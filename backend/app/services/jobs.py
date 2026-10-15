from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models import AuditLog, Event, ProcessingJob, utc_now
from app.services.video_analyzer import scan_video_motion


def _process_claimed_job(session_factory: sessionmaker[Session], settings: Settings, job_id: str) -> None:
    with session_factory() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None or job.status != "running":
            return
        job_snapshot = {
            "organization_id": job.organization_id,
            "requested_by": job.requested_by,
            "input_ref": job.input_ref,
            "site_id": job.site_id,
        }

    try:
        input_path = Path(job_snapshot["input_ref"]).resolve()
        if not input_path.is_relative_to(settings.media_root) or not input_path.is_file():
            raise ValueError("Uploaded media is unavailable or outside the configured media directory")
        observations = list(scan_video_motion(
            input_path,
            frame_stride=settings.video_frame_stride,
            threshold=settings.video_motion_threshold,
            min_gap_seconds=settings.video_min_gap_seconds,
            max_duration_seconds=settings.max_video_duration_seconds,
            max_frames=settings.max_video_frames,
        ))
        with session_factory() as db:
            job = db.get(ProcessingJob, job_id)
            if job is None or job.status != "running":
                return
            base_time = job.created_at or utc_now()
            if base_time.tzinfo is None:
                base_time = base_time.replace(tzinfo=utc_now().tzinfo)
            snapshots_dir = settings.media_root / job.organization_id / "snapshots"
            snapshots_dir.mkdir(parents=True, exist_ok=True)
            for index, item in enumerate(observations):
                snapshot_ref = None
                if item.snapshot_bytes:
                    snapshot_filename = f"{job.id}_{index}.jpg"
                    (snapshots_dir / snapshot_filename).write_bytes(item.snapshot_bytes)
                    snapshot_ref = f"snapshots/{snapshot_filename}"
                is_semantic = bool(getattr(item, "is_semantic", False))
                primary_label = getattr(item, "primary_label", None)
                detected_objs = list(getattr(item, "detected_objects", ()))

                db.add(Event(
                    organization_id=job.organization_id,
                    site_id=job.site_id,
                    source_id=f"video-job:{job.id}",
                    event_type="motion_observed",
                    observed_at=base_time + timedelta(seconds=item.timestamp_seconds),
                    review_status="unreviewed",
                    score=item.foreground_ratio,
                    score_kind="foreground_pixel_ratio",
                    evidence_ref=f"job:{job.id}",
                    model_version="yolov8n-onnx-v1" if is_semantic else "opencv-mog2-motion-v1",
                    details={
                        "method": "yolov8_edge_detection" if is_semantic else "background_subtraction",
                        "semantic_classification": is_semantic,
                        "primary_label": primary_label,
                        "detected_objects": detected_objs,
                        "frame_timestamp_seconds": item.timestamp_seconds,
                        "interpretation": (
                            f"Detected {primary_label} via local edge AI model; operator verification required."
                            if is_semantic
                            else "Generic scene motion only; not object identity or threat assessment."
                        ),
                        "snapshot_ref": snapshot_ref,
                        "job_id": job.id,
                        "bounding_boxes": list(item.boxes),
                        "box_count": len(item.boxes),
                    },
                    dedupe_key=f"{job.id}:motion:{index}",
                ))
            job.status = "succeeded"
            job.last_heartbeat_at = utc_now()
            job.result_summary = {"motion_events_created": len(observations), "analysis_type": "generic_video_motion_scan", "model_version": "opencv-mog2-motion-v1"}
            job.finished_at = utc_now()
            job.error_message = None
            db.add(AuditLog(organization_id=job.organization_id, actor_id=job.requested_by, action="analysis.job.complete", resource_type="processing_job", resource_id=job.id, details=job.result_summary))
            db.commit()

            from app.core.ws_manager import ws_manager
            ws_manager.broadcast_threadsafe(
                job.organization_id,
                {
                    "type": "JOB_COMPLETED",
                    "job_id": job.id,
                    "site_id": job.site_id,
                    "status": "succeeded",
                    "events_created": len(observations),
                }
            )
            for idx, item in enumerate(observations):
                ws_manager.broadcast_threadsafe(
                    job.organization_id,
                    {
                        "type": "NEW_ALERT",
                        "event": {
                            "id": f"{job.id}:motion:{idx}",
                            "site_id": job.site_id,
                            "source_id": f"video-job:{job.id}",
                            "event_type": "motion_observed",
                            "score": item.foreground_ratio,
                            "score_kind": "foreground_pixel_ratio",
                            "observed_at": (base_time + timedelta(seconds=item.timestamp_seconds)).isoformat(),
                            "review_status": "unreviewed",
                            "primary_label": getattr(item, "primary_label", None),
                            "is_semantic": bool(getattr(item, "is_semantic", False)),
                            "snapshot_url": f"/api/v1/events/{job.id}_{idx}/snapshot" if item.snapshot_bytes else None,
                        }
                    }
                )
    except Exception as exc:
        with session_factory() as db:
            job = db.get(ProcessingJob, job_id)
            if job is not None:
                job.status = "failed"
                job.finished_at = utc_now()
                job.error_message = f"{type(exc).__name__}: {str(exc)[:500]}"
                db.add(AuditLog(organization_id=job.organization_id, actor_id=job.requested_by, action="analysis.job.fail", resource_type="processing_job", resource_id=job.id, outcome="failure", details={"error_type": type(exc).__name__}))
                db.commit()


def process_job(session_factory: sessionmaker[Session], settings: Settings, job_id: str) -> None:
    """Claim a specific queued job then process it (useful for test/support tooling)."""
    with session_factory() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None or job.status != "queued":
            return
        job.status = "running"
        job.started_at = utc_now()
        job.last_heartbeat_at = utc_now()
        job.attempts += 1
        job.error_message = None
        db.commit()
    _process_claimed_job(session_factory, settings, job_id)


def _recover_stale_jobs(session_factory: sessionmaker[Session], settings: Settings) -> None:
    """Recover work left running after a worker crash; supports both lease timeout and fast heartbeat."""
    cutoff = utc_now() - timedelta(minutes=settings.job_stale_minutes)
    hb_timeout = getattr(settings, "job_heartbeat_timeout_seconds", 90)
    hb_cutoff = utc_now() - timedelta(seconds=hb_timeout)
    with session_factory() as db:
        stale_condition = (
            (ProcessingJob.started_at.is_not(None) & (ProcessingJob.started_at < cutoff))
            | (ProcessingJob.last_heartbeat_at.is_not(None) & (ProcessingJob.last_heartbeat_at < hb_cutoff))
        )
        stale_jobs = list(db.scalars(select(ProcessingJob).where(ProcessingJob.status == "running", stale_condition)).all())
        for job in stale_jobs:
            if job.attempts < settings.max_job_attempts:
                job.status = "queued"
                job.error_message = "Recovered after worker lease expired; job requeued."
                job.started_at = None
                job.last_heartbeat_at = None
            else:
                job.status = "failed"
                job.error_message = "Worker lease expired and maximum attempts were reached."
                job.finished_at = utc_now()
        if stale_jobs:
            db.commit()


def run_once(session_factory: sessionmaker[Session], settings: Settings) -> bool:
    """Claim the oldest queued job and process it. Deploy one worker per DB until load-tested."""
    _recover_stale_jobs(session_factory, settings)
    with session_factory() as db:
        query = select(ProcessingJob).where(ProcessingJob.status == "queued", ProcessingJob.attempts < settings.max_job_attempts).order_by(ProcessingJob.created_at.asc()).limit(1).with_for_update(skip_locked=True)
        job = db.scalar(query)
        if job is None:
            return False
        job.status = "running"
        job.started_at = utc_now()
        job.last_heartbeat_at = utc_now()
        job.attempts += 1
        job.error_message = None
        job_id = job.id
        db.commit()
    _process_claimed_job(session_factory, settings, job_id)
    return True
