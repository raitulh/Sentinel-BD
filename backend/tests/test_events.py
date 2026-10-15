from __future__ import annotations

from datetime import datetime, timezone

from app.core.security import hash_password
from app.models import Organization, User


def create_event(client, headers, **overrides):
    body = {"source_id": "camera-01", "event_type": "motion_observed", "observed_at": datetime.now(timezone.utc).isoformat(), "score": 0.35, "score_kind": "foreground_pixel_ratio", "details": {"synthetic": True}}
    body.update(overrides)
    return client.post("/api/v1/events", headers=headers, json=body)


def test_create_and_list_event(client, auth_headers):
    response = create_event(client, auth_headers)
    assert response.status_code == 201, response.text
    event = response.json()
    assert event["review_status"] == "unreviewed"
    assert event["score"] == 0.35
    listing = client.get("/api/v1/events?limit=10&offset=0", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == event["id"]


def test_event_score_out_of_range_rejected(client, auth_headers):
    response = create_event(client, auth_headers, score=1.5)
    assert response.status_code == 422


def test_partial_coordinates_rejected(client, auth_headers):
    response = create_event(client, auth_headers, latitude=23.7)
    assert response.status_code == 422


def test_score_kind_without_score_rejected(client, auth_headers):
    response = create_event(client, auth_headers, score=None)
    # score_kind remains present, so the request is invalid.
    assert response.status_code == 422


def test_event_filter_and_pagination(client, auth_headers):
    create_event(client, auth_headers, event_type="motion_observed", source_id="cam-a")
    create_event(client, auth_headers, event_type="sample_observation", source_id="cam-b")
    filtered = client.get("/api/v1/events?event_type=motion_observed&limit=1", headers=auth_headers)
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert len(filtered.json()["items"]) == 1


def test_review_marks_event_reviewed(client, auth_headers):
    event = create_event(client, auth_headers).json()
    response = client.post(f"/api/v1/events/{event['id']}/reviews", headers=auth_headers, json={"decision": "false_positive", "note": "Synthetic test review"})
    assert response.status_code == 201, response.text
    assert response.json()["decision"] == "false_positive"
    current = client.get(f"/api/v1/events/{event['id']}", headers=auth_headers).json()
    assert current["review_status"] == "reviewed"
    reviews = client.get(f"/api/v1/events/{event['id']}/reviews", headers=auth_headers)
    assert reviews.status_code == 200 and len(reviews.json()) == 1


def test_event_not_found_is_404(client, auth_headers):
    response = client.get("/api/v1/events/not-a-real-id", headers=auth_headers)
    assert response.status_code == 404


def test_tenant_isolation_prevents_cross_org_event_read(client, app, auth_headers):
    response = create_event(client, auth_headers)
    event_id = response.json()["id"]
    factory = app.state.session_factory
    with factory() as db:
        org = Organization(name="Other Org")
        db.add(org); db.flush()
        other_user = User(organization_id=org.id, email="other@example.test", password_hash=hash_password("another-correct-password-77"), role="admin", is_active=True)
        db.add(other_user); db.commit()
    login = client.post("/api/v1/auth/login", json={"email": "other@example.test", "password": "another-correct-password-77"})
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(f"/api/v1/events/{event_id}", headers=other_headers).status_code == 404
    assert client.get("/api/v1/events", headers=other_headers).json()["total"] == 0


def test_viewer_cannot_create_event(client, auth_headers):
    created = client.post("/api/v1/users", headers=auth_headers, json={"email": "viewer@example.test", "password": "viewer-correct-password-88", "role": "viewer"})
    assert created.status_code == 201, created.text
    login = client.post("/api/v1/auth/login", json={"email": "viewer@example.test", "password": "viewer-correct-password-88"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert create_event(client, headers).status_code == 403


def test_user_admin_endpoints_forbidden_to_viewer(client, auth_headers):
    created = client.post("/api/v1/users", headers=auth_headers, json={"email": "viewer@example.test", "password": "viewer-correct-password-88", "role": "viewer"})
    login = client.post("/api/v1/auth/login", json={"email": "viewer@example.test", "password": "viewer-correct-password-88"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/users", headers=headers).status_code == 403
    assert client.post("/api/v1/sites", headers=headers, json={"name": "Cannot create"}).status_code == 403


def test_duplicate_user_email_rejected(client, auth_headers):
    body = {"email": "new@example.test", "password": "a-long-enough-password-123", "role": "viewer"}
    assert client.post("/api/v1/users", headers=auth_headers, json=body).status_code == 201
    assert client.post("/api/v1/users", headers=auth_headers, json=body).status_code == 409


def test_admin_can_deactivate_user_and_tokens_stop_working(client, auth_headers):
    created = client.post("/api/v1/users", headers=auth_headers, json={"email": "disable-me@example.test", "password": "disable-correct-password-77", "role": "viewer"})
    assert created.status_code == 201
    user_id = created.json()["id"]
    login = client.post("/api/v1/auth/login", json={"email": "disable-me@example.test", "password": "disable-correct-password-77"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=viewer_headers).status_code == 200
    disabled = client.patch(f"/api/v1/users/{user_id}/active", headers=auth_headers, json={"is_active": False})
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False
    assert client.get("/api/v1/auth/me", headers=viewer_headers).status_code == 401


def test_last_admin_cannot_deactivate_self(client, auth_headers, admin):
    response = client.patch(f"/api/v1/users/{admin['user']['id']}/active", headers=auth_headers, json={"is_active": False})
    assert response.status_code == 409
    assert "own account" in response.json()["detail"]


def test_deactivated_user_cannot_login(client, auth_headers):
    created = client.post("/api/v1/users", headers=auth_headers, json={"email": "disabled-login@example.test", "password": "disabled-login-pass-77", "role": "viewer"}).json()
    client.patch(f"/api/v1/users/{created['id']}/active", headers=auth_headers, json={"is_active": False})
    response = client.post("/api/v1/auth/login", json={"email": "disabled-login@example.test", "password": "disabled-login-pass-77"})
    assert response.status_code == 401


def test_naive_event_timestamp_is_normalized_to_utc(client, auth_headers):
    response = create_event(client, auth_headers, observed_at="2026-10-14T12:00:00")
    assert response.status_code == 201
    assert response.json()["observed_at"].endswith("Z") or response.json()["observed_at"].endswith("+00:00")
