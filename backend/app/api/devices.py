from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_roles
from app.models import AuditLog, Device, Site, User
from app.schemas import DeviceCreate, DevicePublic, HeartbeatRequest

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("", response_model=DevicePublic, status_code=status.HTTP_201_CREATED)
def create_device(body: DeviceCreate, db: DbSession, user: User = Depends(require_roles("admin", "operator"))):
    if body.site_id:
        site = db.scalar(select(Site).where(Site.id == body.site_id, Site.organization_id == user.organization_id))
        if site is None:
            raise HTTPException(status_code=404, detail="Site not found")
    device = Device(organization_id=user.organization_id, site_id=body.site_id, name=body.name.strip(), device_type=body.device_type, status=body.status, metadata_json=body.details)
    db.add(device)
    db.flush()
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action="device.create", resource_type="device", resource_id=device.id, details={"name": device.name, "device_type": device.device_type}))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(device)
    return device


@router.get("", response_model=list[DevicePublic])
def list_devices(db: DbSession, user: CurrentUser):
    return list(db.scalars(select(Device).where(Device.organization_id == user.organization_id).order_by(Device.created_at.desc())).all())


@router.get("/{device_id}", response_model=DevicePublic)
def get_device(device_id: str, db: DbSession, user: CurrentUser):
    device = db.scalar(select(Device).where(Device.id == device_id, Device.organization_id == user.organization_id))
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("/{device_id}/heartbeat", response_model=DevicePublic)
def heartbeat(device_id: str, body: HeartbeatRequest, db: DbSession, user: User = Depends(require_roles("admin", "operator"))):
    device = db.scalar(select(Device).where(Device.id == device_id, Device.organization_id == user.organization_id))
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    device.status = body.status
    device.last_seen_at = datetime.now(timezone.utc)
    device.metadata_json = {**(device.metadata_json or {}), "last_heartbeat_details": body.details}
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action="device.heartbeat", resource_type="device", resource_id=device.id, details={"status": body.status}))
    db.commit()
    db.refresh(device)
    return device
