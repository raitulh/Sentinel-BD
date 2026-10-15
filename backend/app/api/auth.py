from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models import AuditLog, Organization, User, utc_now
from app.schemas import BootstrapRequest, LoginRequest, TokenResponse, UserPublic

router = APIRouter(prefix="/auth", tags=["authentication"])


def _user_payload(user: User) -> UserPublic:
    return UserPublic.model_validate(user)


@router.post("/bootstrap", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def bootstrap(
    body: BootstrapRequest,
    request: Request,
    db: DbSession,
    bootstrap_header: Annotated[str | None, Header(alias="X-Bootstrap-Token")] = None,
) -> TokenResponse:
    configured = request.app.state.settings.bootstrap_token
    if not configured or not bootstrap_header or not hmac.compare_digest(configured, bootstrap_header):
        raise HTTPException(status_code=403, detail="Bootstrap is disabled or token is invalid")
    if db.scalar(select(func.count()).select_from(User)):
        raise HTTPException(status_code=409, detail="Bootstrap has already been completed")
    org = Organization(name=body.organization_name.strip())
    db.add(org)
    db.flush()
    try:
        user = User(organization_id=org.id, email=body.email, password_hash=hash_password(body.password), role="admin", is_active=True)
        db.add(user)
        db.flush()
        db.add(AuditLog(organization_id=org.id, actor_id=user.id, action="auth.bootstrap", resource_type="organization", resource_id=org.id, details={"email": user.email}))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bootstrap could not create the initial account") from exc
    expires = request.app.state.settings.access_token_minutes * 60
    token = create_access_token(user_id=user.id, organization_id=org.id, role=user.role, secret_key=request.app.state.settings.secret_key, expires_seconds=expires)
    return TokenResponse(access_token=token, expires_in=expires, user=_user_payload(user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: DbSession) -> TokenResponse:
    # Generic error avoids account enumeration by email.
    user = db.scalar(select(User).where(User.email == body.email).limit(1))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password", headers={"WWW-Authenticate": "Bearer"})
    expires = request.app.state.settings.access_token_minutes * 60
    token = create_access_token(user_id=user.id, organization_id=user.organization_id, role=user.role, secret_key=request.app.state.settings.secret_key, expires_seconds=expires)
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action="auth.login", resource_type="user", resource_id=user.id, details={}))
    db.commit()
    return TokenResponse(access_token=token, expires_in=expires, user=_user_payload(user))


@router.get("/me", response_model=UserPublic)
def me(user: CurrentUser) -> UserPublic:
    return _user_payload(user)
