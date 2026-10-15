from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_roles
from app.models import AuditLog, Site, User
from app.schemas import SiteCreate, SitePublic

router = APIRouter(prefix="/sites", tags=["sites"])


@router.post("", response_model=SitePublic, status_code=status.HTTP_201_CREATED)
def create_site(body: SiteCreate, db: DbSession, user: User = Depends(require_roles("admin", "operator"))):
    site = Site(organization_id=user.organization_id, name=body.name.strip(), description=body.description, latitude=body.latitude, longitude=body.longitude)
    db.add(site)
    db.flush()
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action="site.create", resource_type="site", resource_id=site.id, details={"name": site.name}))
    db.commit()
    db.refresh(site)
    return site


@router.get("", response_model=list[SitePublic])
def list_sites(db: DbSession, user: CurrentUser):
    return list(db.scalars(select(Site).where(Site.organization_id == user.organization_id).order_by(Site.name)).all())


@router.get("/{site_id}", response_model=SitePublic)
def get_site(site_id: str, db: DbSession, user: CurrentUser):
    site = db.scalar(select(Site).where(Site.id == site_id, Site.organization_id == user.organization_id))
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return site
