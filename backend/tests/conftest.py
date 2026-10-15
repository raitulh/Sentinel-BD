from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def app(tmp_path: Path):
    test_app = create_app(
        database_url="sqlite://",
        bootstrap_token="test-bootstrap-token-0123456789",
        secret_key="test-secret-key-that-is-long-enough-for-unit-tests-123456",
        app_env="test",
        media_root=tmp_path / "media",
        auto_create_tables=True,
    )
    # Test-specific small upload limit and deterministic motion settings.
    test_app.state.settings = replace(
        test_app.state.settings,
        max_upload_bytes=2 * 1024 * 1024,
        video_frame_stride=2,
        video_motion_threshold=0.01,
        video_min_gap_seconds=0.1,
    )
    return test_app


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin(client):
    response = client.post(
        "/api/v1/auth/bootstrap",
        headers={"X-Bootstrap-Token": "test-bootstrap-token-0123456789"},
        json={"organization_name": "Test Lab", "email": "admin@example.test", "password": "correct-horse-battery-77"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return {"token": payload["access_token"], "user": payload["user"]}


@pytest.fixture
def auth_headers(admin):
    return {"Authorization": f"Bearer {admin['token']}"}
