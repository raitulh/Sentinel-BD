from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = "Sentinel BD API"
    app_env: str = "development"
    secret_key: str = ""
    bootstrap_token: str = ""
    database_url: str = "sqlite:///./sentinel.db"
    media_root: Path = Path("./data/media")
    max_upload_bytes: int = 200 * 1024 * 1024
    access_token_minutes: int = 30
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
    log_level: str = "INFO"
    video_frame_stride: int = 5
    video_motion_threshold: float = 0.08
    video_min_gap_seconds: float = 2.0
    max_video_duration_seconds: int = 3600
    max_video_frames: int = 100000
    worker_poll_seconds: float = 2.0
    job_stale_minutes: int = 180
    job_heartbeat_timeout_seconds: int = 90
    max_job_attempts: int = 3

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.getenv("APP_ENV", "development").lower()
        secret = os.getenv("SECRET_KEY", "")
        if not secret and env == "development":
            secret = "development-only-change-me-not-for-production-32chars"
        settings = cls(
            app_name=os.getenv("APP_NAME", "Sentinel BD API"),
            app_env=env,
            secret_key=secret,
            bootstrap_token=os.getenv("BOOTSTRAP_TOKEN", ""),
            database_url=os.getenv("DATABASE_URL", "sqlite:///./sentinel.db"),
            media_root=Path(os.getenv("MEDIA_ROOT", "./data/media")).expanduser().resolve(),
            max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(200 * 1024 * 1024))),
            access_token_minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "30")),
            cors_origins=tuple(_csv(os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"))),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            video_frame_stride=max(1, int(os.getenv("VIDEO_FRAME_STRIDE", "5"))),
            video_motion_threshold=float(os.getenv("VIDEO_MOTION_THRESHOLD", "0.08")),
            video_min_gap_seconds=max(0.0, float(os.getenv("VIDEO_MIN_GAP_SECONDS", "2.0"))),
            max_video_duration_seconds=max(1, int(os.getenv("MAX_VIDEO_DURATION_SECONDS", "3600"))),
            max_video_frames=max(1, int(os.getenv("MAX_VIDEO_FRAMES", "100000"))),
            worker_poll_seconds=max(0.25, float(os.getenv("WORKER_POLL_SECONDS", "2.0"))),
            job_stale_minutes=max(5, int(os.getenv("JOB_STALE_MINUTES", "180"))),
            job_heartbeat_timeout_seconds=max(10, int(os.getenv("JOB_HEARTBEAT_TIMEOUT_SECONDS", "90"))),
            max_job_attempts=max(1, int(os.getenv("MAX_JOB_ATTEMPTS", "3"))),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.app_env == "production":
            if len(self.secret_key) < 32 or self.secret_key.startswith("development-only") or "replace-this" in self.secret_key.lower() or "change-me" in self.secret_key.lower():
                raise ValueError("Production requires a strong SECRET_KEY of at least 32 characters")
            if not self.bootstrap_token or len(self.bootstrap_token) < 24 or "replace-this" in self.bootstrap_token.lower() or "change-me" in self.bootstrap_token.lower():
                raise ValueError("Production requires BOOTSTRAP_TOKEN (at least 24 characters)")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS is not allowed in production")
        if self.app_env == "production":
            if self.database_url.startswith("sqlite"):
                raise ValueError("Production requires PostgreSQL; SQLite is only for development/testing")
            if "replace-this" in self.database_url.lower() or "change-me" in self.database_url.lower():
                raise ValueError("Production DATABASE_URL still contains a placeholder password")
        if self.max_upload_bytes < 1024:
            raise ValueError("MAX_UPLOAD_BYTES must be at least 1024")
        if not 0.0 <= self.video_motion_threshold <= 1.0:
            raise ValueError("VIDEO_MOTION_THRESHOLD must be between 0 and 1")
        if self.access_token_minutes < 1:
            raise ValueError("ACCESS_TOKEN_MINUTES must be positive")
        if self.max_video_duration_seconds < 1 or self.max_video_frames < 1:
            raise ValueError("Video duration and frame limits must be positive")
