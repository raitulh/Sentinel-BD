from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.security import hash_password  # noqa: E402
from app.database import Base, make_engine, make_session_factory  # noqa: E402
from app.models import Organization, User  # noqa: E402


def main() -> None:
    if os.getenv("APP_ENV", "development").lower() == "production":
        raise SystemExit("Do not use this development helper in production; run migrations and use the protected bootstrap endpoint.")
    database_url = os.getenv("DATABASE_URL", "sqlite:///./sentinel.db")
    engine = make_engine(database_url)
    Base.metadata.create_all(bind=engine)
    factory = make_session_factory(engine)
    organization_name = input("Organization / lab name: ").strip()
    email = input("Admin email: ").strip().lower()
    password = getpass.getpass("Password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    with factory() as db:
        if db.query(User).count():
            raise SystemExit("At least one user already exists. Initial-admin creation is disabled.")
        org = Organization(name=organization_name)
        db.add(org)
        db.flush()
        db.add(User(organization_id=org.id, email=email, password_hash=hash_password(password), role="admin", is_active=True))
        db.commit()
    engine.dispose()
    print("Initial administrator created. Change database and secret configuration before production use.")


if __name__ == "__main__":
    main()
