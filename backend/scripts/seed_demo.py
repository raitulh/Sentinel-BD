from __future__ import annotations

import os
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.security import hash_password  # noqa: E402
from app.database import Base, make_engine, make_session_factory  # noqa: E402
from app.models import Device, Event, Organization, Site, User  # noqa: E402


def main() -> None:
    if os.getenv("APP_ENV", "development").lower() == "production":
        raise SystemExit("Demo seeding is disabled in production.")
    if os.getenv("ALLOW_DEMO_SEED", "false").lower() != "true":
        raise SystemExit("Set ALLOW_DEMO_SEED=true to confirm that this is a disposable demo environment.")
    engine = make_engine(os.getenv("DATABASE_URL", "sqlite:///./sentinel.db"))
    Base.metadata.create_all(bind=engine)
    factory = make_session_factory(engine)
    with factory() as db:
        email = os.getenv("DEMO_EMAIL", "admin@example.local").lower()
        if db.query(User).filter_by(email=email).first():
            raise SystemExit("Demo user already exists; refusing to overwrite")
        org = Organization(name="Sentinel Demo Lab")
        db.add(org); db.flush()
        user = User(organization_id=org.id, email=email, password_hash=hash_password(os.getenv("DEMO_PASSWORD", "LocalDemoOnly-ChangeMe!")), role="admin", is_active=True)
        db.add(user); db.flush()
        site = Site(organization_id=org.id, name="Demo Test Site", description="Synthetic demonstration only")
        db.add(site); db.flush()
        db.add(Device(organization_id=org.id, site_id=site.id, name="Synthetic Camera 01", device_type="simulator", status="active", metadata_json={"synthetic": True}))
        db.add(Event(organization_id=org.id, site_id=site.id, source_id="synthetic-camera-01", event_type="sample_observation", observed_at=datetime.now(timezone.utc), review_status="unreviewed", score=0.42, score_kind="demo_score_not_probability", details={"synthetic": True, "note": "Demo seed data; not a real detection."}))
        db.commit()
    engine.dispose()
    print(f"Seeded demo-only workspace for {email}. Change DEMO_PASSWORD before use; never seed demo records in production.")


if __name__ == "__main__":
    main()
