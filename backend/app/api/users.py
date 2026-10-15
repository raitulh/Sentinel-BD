from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.security import hash_password
from app.models import AuditLog, User
from app.schemas import UserActiveUpdate, UserCreate, UserPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserPublic])
def list_users(db: DbSession, user: User = Depends(require_roles("admin"))):
    return list(db.scalars(select(User).where(User.organization_id == user.organization_id).order_by(User.email)).all())


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: DbSession, user: User = Depends(require_roles("admin"))):
    if db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    try:
        new_user = User(organization_id=user.organization_id, email=body.email, password_hash=hash_password(body.password), role=body.role, is_active=True)
        db.add(new_user)
        db.flush()
        db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action="user.create", resource_type="user", resource_id=new_user.id, details={"email": new_user.email, "role": new_user.role}))
        db.commit()
        db.refresh(new_user)
        return new_user
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Unable to create user; email may already be in use") from exc


@router.patch("/{user_id}/active", response_model=UserPublic)
def set_user_active(user_id: str, body: UserActiveUpdate, db: DbSession, user: User = Depends(require_roles("admin"))):
    target = db.scalar(select(User).where(User.id == user_id, User.organization_id == user.organization_id))
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == user.id and not body.is_active:
        raise HTTPException(status_code=409, detail="Administrators cannot deactivate their own account")
    if target.role == "admin" and target.is_active and not body.is_active:
        active_admins = db.scalar(select(func.count()).select_from(User).where(User.organization_id == user.organization_id, User.role == "admin", User.is_active.is_(True))) or 0
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="The last active administrator cannot be deactivated")
    target.is_active = body.is_active
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action="user.set_active", resource_type="user", resource_id=target.id, details={"is_active": body.is_active}))
    db.commit()
    db.refresh(target)
    return target
