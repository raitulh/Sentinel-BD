from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession, get_db, require_roles
from app.models import AuditLog, Event, EventReview, ProcessingJob, Site
from app.schemas import EventCreate, EventList, EventPublic, ReviewCreate, ReviewPublic

router = APIRouter(prefix="/events", tags=["events"])


def _validate_site(db: Session, organization_id: str, site_id: str | None) -> None:
    if site_id and db.scalar(select(Site.id).where(Site.id == site_id, Site.organization_id == organization_id)) is None:
        raise HTTPException(status_code=404, detail="Site not found")


@router.post("", response_model=EventPublic, status_code=status.HTTP_201_CREATED)
def create_event(body: EventCreate, db: DbSession, user=Depends(require_roles("admin", "operator", "reviewer"))):
    _validate_site(db, user.organization_id, body.site_id)
    event = Event(
        organization_id=user.organization_id,
        site_id=body.site_id,
        source_id=body.source_id,
        event_type=body.event_type,
        observed_at=body.observed_at,
        review_status="unreviewed",
        score=body.score,
        score_kind=body.score_kind,
        evidence_ref=body.evidence_ref,
        model_version=body.model_version,
        details=body.details,
        latitude=body.latitude,
        longitude=body.longitude,
    )
    db.add(event)
    db.flush()
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action="event.create", resource_type="event", resource_id=event.id, details={"event_type": event.event_type, "source_id": event.source_id}))
    db.commit()
    db.refresh(event)

    from app.core.ws_manager import ws_manager
    ws_manager.broadcast_threadsafe(
        user.organization_id,
        {
            "type": "NEW_ALERT",
            "event": {
                "id": event.id,
                "site_id": event.site_id,
                "source_id": event.source_id,
                "event_type": event.event_type,
                "observed_at": event.observed_at.isoformat(),
                "review_status": event.review_status,
                "score": event.score,
                "score_kind": event.score_kind,
                "primary_label": event.details.get("primary_label") if event.details else None,
                "is_semantic": bool(event.details.get("semantic_classification", False)) if event.details else False,
            }
        }
    )
    return event


@router.get("", response_model=EventList)
def list_events(
    db: DbSession,
    user: CurrentUser,
    site_id: str | None = None,
    event_type: str | None = Query(default=None, max_length=80),
    review_status: str | None = Query(default=None, pattern="^(unreviewed|reviewed)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1_000_000),
):
    conditions = [Event.organization_id == user.organization_id]
    if site_id:
        conditions.append(Event.site_id == site_id)
    if event_type:
        conditions.append(Event.event_type == event_type)
    if review_status:
        conditions.append(Event.review_status == review_status)
    total = db.scalar(select(func.count()).select_from(Event).where(*conditions)) or 0
    items = db.scalars(select(Event).where(*conditions).order_by(Event.observed_at.desc(), Event.id.desc()).limit(limit).offset(offset)).all()
    return EventList(items=list(items), total=total, limit=limit, offset=offset)


@router.get("/{event_id}", response_model=EventPublic)
def get_event(event_id: str, db: DbSession, user: CurrentUser):
    event = db.scalar(select(Event).where(Event.id == event_id, Event.organization_id == user.organization_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/{event_id}/reviews", response_model=ReviewPublic, status_code=status.HTTP_201_CREATED)
def review_event(event_id: str, body: ReviewCreate, db: DbSession, user=Depends(require_roles("admin", "operator", "reviewer"))):
    event = db.scalar(select(Event).where(Event.id == event_id, Event.organization_id == user.organization_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    review = EventReview(organization_id=user.organization_id, event_id=event.id, reviewer_id=user.id, decision=body.decision, note=body.note)
    event.review_status = "reviewed"
    db.add(review)
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action="event.review", resource_type="event", resource_id=event.id, details={"decision": body.decision}))
    db.commit()
    db.refresh(review)
    return review


@router.get("/{event_id}/reviews", response_model=list[ReviewPublic])
def list_reviews(event_id: str, db: DbSession, user: CurrentUser):
    event = db.scalar(select(Event.id).where(Event.id == event_id, Event.organization_id == user.organization_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return list(db.scalars(select(EventReview).where(EventReview.event_id == event_id, EventReview.organization_id == user.organization_id).order_by(EventReview.created_at.desc())).all())


@router.get("/{event_id}/snapshot")
def get_event_snapshot(event_id: str, db: DbSession, user: CurrentUser):
    event = db.scalar(select(Event).where(Event.id == event_id, Event.organization_id == user.organization_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    snapshot_ref = event.details.get("snapshot_ref") if isinstance(event.details, dict) else None
    if not snapshot_ref:
        raise HTTPException(status_code=404, detail="No snapshot available for this event")
    settings = getattr(db, "_sentinel_settings", None)
    if settings is None:
        raise HTTPException(status_code=500, detail="Storage configuration unavailable")
    snapshot_path = (settings.media_root / user.organization_id / snapshot_ref).resolve()
    if not snapshot_path.is_relative_to(settings.media_root) or not snapshot_path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot file not found on disk")
    return FileResponse(snapshot_path, media_type="image/jpeg", filename=f"event_{event_id}.jpg")


@router.get("/{event_id}/video")
def get_event_video(event_id: str, db: DbSession, user: CurrentUser):
    event = db.scalar(select(Event).where(Event.id == event_id, Event.organization_id == user.organization_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    job_id = None
    if isinstance(event.details, dict) and event.details.get("job_id"):
        job_id = event.details["job_id"]
    elif event.source_id.startswith("video-job:"):
        job_id = event.source_id.replace("video-job:", "")
    elif event.evidence_ref and event.evidence_ref.startswith("job:"):
        job_id = event.evidence_ref.replace("job:", "")
    if not job_id:
        raise HTTPException(status_code=404, detail="No associated video job for this event")
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id, ProcessingJob.organization_id == user.organization_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Associated video job not found")
    settings = getattr(db, "_sentinel_settings", None)
    if settings is None:
        raise HTTPException(status_code=500, detail="Storage configuration unavailable")
    video_path = Path(job.input_ref).resolve()
    if not video_path.is_relative_to(settings.media_root) or not video_path.is_file():
        raise HTTPException(status_code=404, detail="Video media file not found")
    ext = video_path.suffix.lower()
    media_type = "video/mp4" if ext == ".mp4" else ("video/quicktime" if ext == ".mov" else ("video/x-matroska" if ext == ".mkv" else "video/x-msvideo"))
    return FileResponse(video_path, media_type=media_type, filename=job.source_name)
