from __future__ import annotations


def test_security_headers_present(client):
    response = client.get("/health/live")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_audit_log_requires_admin(client, auth_headers):
    response = client.get("/api/v1/audit-logs", headers=auth_headers)
    assert response.status_code == 200
    assert any(row["action"] == "auth.bootstrap" for row in response.json())


def test_viewer_cannot_read_audit_logs(client, auth_headers):
    created = client.post("/api/v1/users", headers=auth_headers, json={"email": "viewer@example.test", "password": "viewer-correct-password-88", "role": "viewer"})
    assert created.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": "viewer@example.test", "password": "viewer-correct-password-88"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/audit-logs", headers=headers).status_code == 403
