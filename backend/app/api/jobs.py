from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession, require_roles
from app.models import AuditLog, ProcessingJob, Site, User
from app.schemas import JobPublic

router = APIRouter(prefix="/analysis/jobs", tags=["analysis jobs"])
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
CHUNK_SIZE = 1024 * 1024


def _job_query(db: Session, job_id: str, organization_id: str) -> ProcessingJob:
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id, ProcessingJob.organization_id == organization_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("", response_model=JobPublic, status_code=status.HTTP_202_ACCEPTED)
def enqueue_video_analysis(
    db: DbSession,
    user: User = Depends(require_roles("admin", "operator")),
    file: UploadFile = File(...),
    site_id: str | None = None,
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported video extension; use mp4, avi, mov, or mkv")
    content_type = (file.content_type or "").lower()
    if not content_type.startswith("video/") and content_type not in {"application/octet-stream", "application/x-matroska"}:
        raise HTTPException(status_code=415, detail="Upload must be a video file")
    if site_id and db.scalar(select(Site.id).where(Site.id == site_id, Site.organization_id == user.organization_id)) is None:
        raise HTTPException(status_code=404, detail="Site not found")

    settings = getattr(db, "_sentinel_settings", None)
    # settings are attached on the per-request session by the application factory.
    if settings is None:
        raise HTTPException(status_code=500, detail="Upload storage configuration is unavailable")
    job_id = str(uuid4())
    org_dir = settings.media_root / user.organization_id
    org_dir.mkdir(parents=True, exist_ok=True)
    target = (org_dir / f"{job_id}{ext}").resolve()
    if not target.is_relative_to(settings.media_root):
        raise HTTPException(status_code=400, detail="Invalid file path")
    max_bytes = settings.max_upload_bytes
    total = 0
    try:
        with target.open("xb") as out:
            while True:
                chunk = file.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(status_code=413, detail=f"Upload exceeds {max_bytes} byte limit")
                out.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        job = ProcessingJob(
            id=job_id,
            organization_id=user.organization_id,
            requested_by=user.id,
            job_type="video_motion_scan",
            status="queued",
            input_ref=str(target),
            source_name=(file.filename or "uploaded-video")[:255],
            site_id=site_id,
        )
        db.add(job)
        db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action="analysis.job.create", resource_type="processing_job", resource_id=job.id, details={"bytes": total, "extension": ext}))
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        if target.exists():
            target.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()


@router.get("", response_model=list[JobPublic])
def list_jobs(db: DbSession, user: CurrentUser, limit: int = Query(default=50, ge=1, le=200)):
    return list(db.scalars(select(ProcessingJob).where(ProcessingJob.organization_id == user.organization_id).order_by(ProcessingJob.created_at.desc()).limit(limit)).all())


@router.get("/{job_id}", response_model=JobPublic)
def get_job(job_id: str, db: DbSession, user: CurrentUser):
    return _job_query(db, job_id, user.organization_id)


@router.post("/{job_id}/retry", response_model=JobPublic)
def retry_job(job_id: str, db: DbSession, user: User = Depends(require_roles("admin", "operator"))):
    job = _job_query(db, job_id, user.organization_id)
    if job.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried")
    if job.attempts >= db._sentinel_settings.max_job_attempts:
        raise HTTPException(status_code=409, detail="Maximum attempts reached; investigate before resubmitting")
    job.status = "queued"
    job.error_message = None
    job.started_at = None
    job.finished_at = None
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action="analysis.job.retry", resource_type="processing_job", resource_id=job.id, details={}))
    db.commit()
    db.refresh(job)
    return job


@router.get("/{job_id}/media")
def get_job_media(job_id: str, db: DbSession, user: CurrentUser):
    job = _job_query(db, job_id, user.organization_id)
    settings = getattr(db, "_sentinel_settings", None)
    if settings is None:
        raise HTTPException(status_code=500, detail="Storage configuration unavailable")
    target = Path(job.input_ref).resolve()
    if not target.is_relative_to(settings.media_root) or not target.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")
    return FileResponse(target, media_type="application/octet-stream", filename=job.source_name)
