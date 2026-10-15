from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Role = Literal["admin", "operator", "reviewer", "viewer", "auditor"]
ReviewDecision = Literal["confirmed", "false_positive", "not_actionable", "needs_follow_up"]
DeviceType = Literal["camera", "sensor", "commercial_drone_telemetry", "edge_computer", "simulator"]
DeviceStatus = Literal["active", "offline", "maintenance"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="before", check_fields=False)
    @classmethod
    def normalize_naive_datetime_to_utc(cls, value: Any) -> Any:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class BootstrapRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def email_shape(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("A valid email address is required")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserPublic(ORMModel):
    id: str
    organization_id: str
    email: str
    role: Role
    is_active: bool
    created_at: datetime


class UserActiveUpdate(BaseModel):
    is_active: bool


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)
    role: Role = "viewer"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("A valid email address is required")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinates_pair(self) -> "SiteCreate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class SitePublic(ORMModel):
    id: str
    organization_id: str
    name: str
    description: str | None
    latitude: float | None
    longitude: float | None
    created_at: datetime


class DeviceCreate(BaseModel):
    site_id: str | None = None
    name: str = Field(min_length=1, max_length=160)
    device_type: DeviceType
    status: DeviceStatus = "active"
    details: dict[str, Any] = Field(default_factory=dict)


class DevicePublic(ORMModel):
    id: str
    organization_id: str
    site_id: str | None
    name: str
    device_type: str
    status: str
    metadata_json: dict[str, Any] = Field(serialization_alias="details", validation_alias="metadata_json")
    last_seen_at: datetime | None
    created_at: datetime


class EventCreate(BaseModel):
    @field_validator("observed_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    site_id: str | None = None
    source_id: str = Field(min_length=1, max_length=160)
    event_type: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.:-]+$")
    observed_at: datetime = Field(default_factory=now_utc)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    score_kind: str | None = Field(default=None, max_length=80)
    evidence_ref: str | None = Field(default=None, max_length=500)
    model_version: str | None = Field(default=None, max_length=100)
    details: dict[str, Any] = Field(default_factory=dict)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_coordinates(self) -> "EventCreate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.score is None and self.score_kind is not None:
            raise ValueError("score_kind requires a score")
        return self


class EventPublic(ORMModel):
    id: str
    organization_id: str
    site_id: str | None
    source_id: str
    event_type: str
    observed_at: datetime
    received_at: datetime
    review_status: str
    score: float | None
    score_kind: str | None
    evidence_ref: str | None
    model_version: str | None
    details: dict[str, Any]
    latitude: float | None
    longitude: float | None
    created_at: datetime


class EventList(BaseModel):
    items: list[EventPublic]
    total: int
    limit: int
    offset: int


class ReviewCreate(BaseModel):
    decision: ReviewDecision
    note: str | None = Field(default=None, max_length=4000)


class ReviewPublic(ORMModel):
    id: str
    organization_id: str
    event_id: str
    reviewer_id: str
    decision: str
    note: str | None
    created_at: datetime


class HeartbeatRequest(BaseModel):
    status: Literal["active", "offline", "maintenance"] = "active"
    details: dict[str, Any] = Field(default_factory=dict)


class JobPublic(ORMModel):
    id: str
    organization_id: str
    requested_by: str
    job_type: str
    status: str
    source_name: str
    site_id: str | None
    attempts: int
    result_summary: dict[str, Any]
    error_message: str | None
    started_at: datetime | None
    last_heartbeat_at: datetime | None = None
    finished_at: datetime | None
    created_at: datetime


class MessageResponse(BaseModel):
    message: str
