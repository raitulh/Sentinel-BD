from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps import DbSession, require_roles
from app.models import AuditLog

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("")
def list_audit_logs(db: DbSession, user=Depends(require_roles("admin", "auditor")), limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0, le=1_000_000)):
    rows = db.scalars(select(AuditLog).where(AuditLog.organization_id == user.organization_id).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)).all()
    return [{"id": r.id, "actor_id": r.actor_id, "action": r.action, "resource_type": r.resource_type, "resource_id": r.resource_id, "outcome": r.outcome, "details": r.details, "created_at": r.created_at} for r in rows]
