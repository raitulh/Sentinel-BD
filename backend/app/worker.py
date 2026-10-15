from __future__ import annotations

import logging
import time

from app.core.config import Settings
from app.services.jobs import run_once
from app.main import app


def main() -> None:
    settings: Settings = app.state.settings
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
    engine = app.state.engine
    # API and worker should point at the same DATABASE_URL and media mount.
    if settings.app_env != "production":
        from app.database import Base as DeclarativeBase
        DeclarativeBase.metadata.create_all(bind=engine)
    session_factory = app.state.session_factory
    logging.getLogger("sentinel.worker").info("Worker started")
    try:
        while True:
            processed = run_once(session_factory, settings)
            if not processed:
                time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        logging.getLogger("sentinel.worker").info("Worker stopping")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
