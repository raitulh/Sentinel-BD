from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api import audit, auth, devices, events, jobs, sites, users, ws
from app.core.config import Settings
from app.core.ws_manager import ws_manager
from app.database import Base, make_engine, make_session_factory
from app import models  # noqa: F401 - registers SQLAlchemy models


def create_app(
    *,
    database_url: str | None = None,
    bootstrap_token: str | None = None,
    secret_key: str | None = None,
    app_env: str | None = None,
    media_root: str | Path | None = None,
    auto_create_tables: bool | None = None,
) -> FastAPI:
    settings = Settings.from_env()
    overrides = {}
    if database_url is not None:
        overrides["database_url"] = database_url
    if bootstrap_token is not None:
        overrides["bootstrap_token"] = bootstrap_token
    if secret_key is not None:
        overrides["secret_key"] = secret_key
    if app_env is not None:
        overrides["app_env"] = app_env
    if media_root is not None:
        overrides["media_root"] = Path(media_root).resolve()
    if overrides:
        settings = replace(settings, **overrides)
    settings.validate()
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    auto_tables = auto_create_tables if auto_create_tables is not None else settings.app_env != "production"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        import asyncio
        ws_manager.set_event_loop(asyncio.get_running_loop())
        settings.media_root.mkdir(parents=True, exist_ok=True)
        if auto_tables:
            Base.metadata.create_all(bind=engine)
        yield
        engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Local-first surveillance and sensor-intelligence API. Video analysis emits generic motion observations only; "
            "it does not identify threats or control weapons."
        ),
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
        openapi_url="/openapi.json" if settings.app_env != "production" else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Bootstrap-Token", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        logging.getLogger("sentinel").warning("Database constraint rejected request")
        return JSONResponse(status_code=409, content={"detail": "A conflicting record or constraint violation was detected"})

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError):
        logging.getLogger("sentinel").exception("Database operation failed", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Database operation failed"})

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(sites.router, prefix="/api/v1")
    app.include_router(devices.router, prefix="/api/v1")
    app.include_router(events.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(audit.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(ws.router, prefix="/api/v1")

    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "alive", "service": "sentinel-bd-api", "version": app.version}

    @app.get("/health/ready", tags=["health"])
    def ready():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return {"status": "ready", "database": "ok"}
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable"})

    return app


app = create_app()
