from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile

import cv2
import numpy as np
from sqlalchemy import select

from app.models import Event
from app.services.jobs import run_once


def make_test_video(path: Path) -> bytes:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (128, 96))
    if not writer.isOpened():
        raise RuntimeError("OpenCV video writer unavailable in test environment")
    for index in range(70):
        frame = np.zeros((96, 128, 3), dtype=np.uint8)
        if index >= 12:
            x = min(90, 3 + (index - 12) * 3)
            cv2.rectangle(frame, (x, 25), (min(127, x + 20), 55), (255, 255, 255), -1)
        writer.write(frame)
    writer.release()
    return path.read_bytes()


def test_upload_rejects_unsupported_extension(client, auth_headers):
    response = client.post("/api/v1/analysis/jobs", headers=auth_headers, files={"file": ("payload.txt", b"not a video", "text/plain")})
    assert response.status_code == 415


def test_upload_rejects_wrong_content_type(client, auth_headers):
    response = client.post("/api/v1/analysis/jobs", headers=auth_headers, files={"file": ("clip.mp4", b"not a video", "text/plain")})
    assert response.status_code == 415


def test_upload_rejects_empty_file(client, auth_headers):
    response = client.post("/api/v1/analysis/jobs", headers=auth_headers, files={"file": ("empty.mp4", b"", "video/mp4")})
    assert response.status_code == 400


def test_upload_rejects_oversized_file(client, auth_headers, app):
    app.state.settings = replace(app.state.settings, max_upload_bytes=1024)
    response = client.post("/api/v1/analysis/jobs", headers=auth_headers, files={"file": ("clip.mp4", b"a" * 2048, "video/mp4")})
    assert response.status_code == 413


def test_video_upload_is_queued_and_is_org_scoped(client, auth_headers):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "clip.avi"
        data = make_test_video(path)
    response = client.post("/api/v1/analysis/jobs", headers=auth_headers, files={"file": ("clip.avi", data, "video/x-msvideo")})
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "queued"
    assert job["source_name"] == "clip.avi"
    media = client.get(f"/api/v1/analysis/jobs/{job['id']}/media", headers=auth_headers)
    assert media.status_code == 200
    assert media.content == data


def test_worker_processes_video_and_creates_nonsemantic_events(client, app, auth_headers):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "moving.avi"
        data = make_test_video(path)
    queued = client.post("/api/v1/analysis/jobs", headers=auth_headers, files={"file": ("moving.avi", data, "video/x-msvideo")}).json()
    worked = run_once(app.state.session_factory, app.state.settings)
    assert worked is True
    job = client.get(f"/api/v1/analysis/jobs/{queued['id']}", headers=auth_headers).json()
    assert job["status"] == "succeeded", job
    assert job["result_summary"]["analysis_type"] == "generic_video_motion_scan"
    factory = app.state.session_factory
    with factory() as db:
        events = list(db.scalars(select(Event).where(Event.source_id == f"video-job:{queued['id']}")).all())
        assert len(events) == job["result_summary"]["motion_events_created"]
        if events:
            assert all(e.event_type == "motion_observed" for e in events)
            assert all(e.details.get("semantic_classification") is False for e in events)
            assert all(e.score_kind == "foreground_pixel_ratio" for e in events)
            first_event = events[0]
            if first_event.details.get("snapshot_ref"):
                snap_resp = client.get(f"/api/v1/events/{first_event.id}/snapshot", headers=auth_headers)
                assert snap_resp.status_code == 200
                assert snap_resp.headers["content-type"] == "image/jpeg"
            vid_resp = client.get(f"/api/v1/events/{first_event.id}/video", headers=auth_headers)
            assert vid_resp.status_code == 200
    assert run_once(app.state.session_factory, app.state.settings) is False



def test_video_analyzer_rejects_duration_limit(tmp_path):
    from app.services.video_analyzer import scan_video_motion
    path = tmp_path / "duration.avi"
    make_test_video(path)
    # The synthetic file is about seven seconds at 10 FPS.
    try:
        list(scan_video_motion(path, max_duration_seconds=2, max_frames=1000))
    except ValueError as exc:
        assert "duration limit" in str(exc)
    else:
        raise AssertionError("Expected a too-long video to be rejected")


def test_video_analyzer_rejects_frame_limit(tmp_path):
    from app.services.video_analyzer import scan_video_motion
    path = tmp_path / "frames.avi"
    make_test_video(path)
    try:
        list(scan_video_motion(path, max_duration_seconds=3600, max_frames=20))
    except ValueError as exc:
        assert "frame limit" in str(exc)
    else:
        raise AssertionError("Expected an over-limit video to be rejected")

def test_invalid_video_job_fails_safely(client, app, auth_headers):
    queued_response = client.post("/api/v1/analysis/jobs", headers=auth_headers, files={"file": ("bad.mp4", b"this-is-not-a-video-file", "video/mp4")})
    assert queued_response.status_code == 202
    job_id = queued_response.json()["id"]
    assert run_once(app.state.session_factory, app.state.settings) is True
    job = client.get(f"/api/v1/analysis/jobs/{job_id}", headers=auth_headers).json()
    assert job["status"] == "failed"
    assert "Could not open uploaded video" in job["error_message"]


def test_failed_job_can_be_retried(client, app, auth_headers):
    created = client.post("/api/v1/analysis/jobs", headers=auth_headers, files={"file": ("bad.mp4", b"bad", "video/mp4")}).json()
    run_once(app.state.session_factory, app.state.settings)
    retry = client.post(f"/api/v1/analysis/jobs/{created['id']}/retry", headers=auth_headers)
    assert retry.status_code == 200
    assert retry.json()["status"] == "queued"


def test_cross_tenant_job_media_not_found(client, app, auth_headers):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "clip.avi"
        data = make_test_video(path)
    queued = client.post("/api/v1/analysis/jobs", headers=auth_headers, files={"file": ("clip.avi", data, "video/x-msvideo")}).json()
    from app.core.security import hash_password
    from app.models import Organization, User
    factory = app.state.session_factory
    with factory() as db:
        org = Organization(name="Other Org"); db.add(org); db.flush()
        db.add(User(organization_id=org.id, email="other@example.test", password_hash=hash_password("another-correct-password-77"), role="admin", is_active=True)); db.commit()
    login = client.post("/api/v1/auth/login", json={"email": "other@example.test", "password": "another-correct-password-77"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(f"/api/v1/analysis/jobs/{queued['id']}/media", headers=headers).status_code == 404


def test_stale_running_job_is_recovered(client, app, admin):
    from datetime import datetime, timedelta, timezone
    from app.models import ProcessingJob
    factory = app.state.session_factory
    with factory() as db:
        job = ProcessingJob(
            organization_id=admin["user"]["organization_id"],
            requested_by=admin["user"]["id"],
            job_type="video_motion_scan",
            status="running",
            input_ref=str((app.state.settings.media_root / admin["user"]["organization_id"] / "missing.mp4").resolve()),
            source_name="stale.mp4",
            attempts=1,
            started_at=datetime.now(timezone.utc) - timedelta(hours=4),
        )
        db.add(job); db.commit(); job_id = job.id
    assert run_once(factory, app.state.settings) is True
    with factory() as db:
        job = db.get(ProcessingJob, job_id)
        assert job.status == "failed"  # Requeued from stale state, then failed cleanly because the media is unavailable.
        assert job.attempts == 2


def test_exhausted_stale_job_is_not_reprocessed(client, app, admin):
    from datetime import datetime, timedelta, timezone
    from app.models import ProcessingJob
    factory = app.state.session_factory
    with factory() as db:
        job = ProcessingJob(
            organization_id=admin["user"]["organization_id"],
            requested_by=admin["user"]["id"],
            job_type="video_motion_scan",
            status="running",
            input_ref=str((app.state.settings.media_root / admin["user"]["organization_id"] / "missing.mp4").resolve()),
            source_name="exhausted.mp4",
            attempts=app.state.settings.max_job_attempts,
            started_at=datetime.now(timezone.utc) - timedelta(hours=4),
        )
        db.add(job); db.commit(); job_id = job.id
    assert run_once(factory, app.state.settings) is False
    with factory() as db:
        job = db.get(ProcessingJob, job_id)
        assert job.status == "failed"
        assert "maximum attempts" in job.error_message


def test_retry_rejected_after_max_attempts(client, app, auth_headers):
    response = client.post("/api/v1/analysis/jobs", headers=auth_headers, files={"file": ("bad.mp4", b"not-video", "video/mp4")})
    job_id = response.json()["id"]
    from app.models import ProcessingJob
    with app.state.session_factory() as db:
        job = db.get(ProcessingJob, job_id)
        job.status = "failed"
        job.attempts = app.state.settings.max_job_attempts
        db.commit()
    retry = client.post(f"/api/v1/analysis/jobs/{job_id}/retry", headers=auth_headers)
    assert retry.status_code == 409
    assert "Maximum attempts" in retry.json()["detail"]
