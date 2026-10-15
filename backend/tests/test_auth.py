from __future__ import annotations


def test_health_endpoints(client):
    assert client.get("/health/live").status_code == 200
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_bootstrap_requires_token(client):
    response = client.post("/api/v1/auth/bootstrap", json={"organization_name": "Test Lab", "email": "admin@example.test", "password": "correct-horse-battery-77"})
    assert response.status_code == 403


def test_bootstrap_creates_first_admin(client, admin):
    assert admin["user"]["role"] == "admin"
    assert admin["user"]["email"] == "admin@example.test"
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200


def test_bootstrap_is_one_time(client, admin):
    response = client.post("/api/v1/auth/bootstrap", headers={"X-Bootstrap-Token": "test-bootstrap-token-0123456789"}, json={"organization_name": "Second Lab", "email": "other@example.test", "password": "correct-horse-battery-99"})
    assert response.status_code == 409


def test_weak_password_is_rejected(client):
    response = client.post("/api/v1/auth/bootstrap", headers={"X-Bootstrap-Token": "test-bootstrap-token-0123456789"}, json={"organization_name": "Test Lab", "email": "admin@example.test", "password": "short"})
    assert response.status_code == 422


def test_login_accepts_valid_credentials(client, admin):
    response = client.post("/api/v1/auth/login", json={"email": "ADMIN@example.test", "password": "correct-horse-battery-77"})
    assert response.status_code == 200
    assert response.json()["user"]["id"] == admin["user"]["id"]


def test_login_fails_with_generic_error(client, admin):
    response = client.post("/api/v1/auth/login", json={"email": "admin@example.test", "password": "wrong-password"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_malformed_or_tampered_token_rejected(client, admin):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer abc.invalid"})
    assert response.status_code == 401


def test_authentication_required(client):
    response = client.get("/api/v1/events")
    assert response.status_code == 401


def test_production_settings_require_real_secrets(monkeypatch):
    from app.core.config import Settings
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("BOOTSTRAP_TOKEN", raising=False)
    try:
        Settings.from_env()
    except ValueError as exc:
        assert "SECRET_KEY" in str(exc)
    else:
        raise AssertionError("production settings accepted default secret")


def test_production_rejects_sqlite_even_with_secrets():
    from app.main import create_app
    try:
        create_app(app_env="production", database_url="sqlite:///./unsafe.db", secret_key="x" * 64, bootstrap_token="y" * 32, auto_create_tables=False)
    except ValueError as exc:
        assert "PostgreSQL" in str(exc)
    else:
        raise AssertionError("production mode allowed SQLite")
