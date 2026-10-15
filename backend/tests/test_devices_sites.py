from __future__ import annotations


def test_create_site_and_device(client, auth_headers):
    site = client.post("/api/v1/sites", headers=auth_headers, json={"name": "Test Site", "latitude": 23.7, "longitude": 90.4})
    assert site.status_code == 201, site.text
    device = client.post("/api/v1/devices", headers=auth_headers, json={"name": "Camera 1", "device_type": "camera", "site_id": site.json()["id"], "details": {"vendor": "test"}})
    assert device.status_code == 201, device.text
    assert device.json()["details"]["vendor"] == "test"
    assert device.json()["site_id"] == site.json()["id"]


def test_site_coordinates_must_be_pair(client, auth_headers):
    response = client.post("/api/v1/sites", headers=auth_headers, json={"name": "Half coordinate site", "latitude": 23.7})
    assert response.status_code == 422


def test_site_coordinate_range_validated(client, auth_headers):
    response = client.post("/api/v1/sites", headers=auth_headers, json={"name": "Bad site", "latitude": 123, "longitude": 91})
    assert response.status_code == 422


def test_device_cannot_reference_another_org_site(client, app, auth_headers):
    factory = app.state.session_factory
    from app.models import Organization, Site, User
    from app.core.security import hash_password
    with factory() as db:
        org = Organization(name="Other Org"); db.add(org); db.flush()
        other_user = User(organization_id=org.id, email="other@example.test", password_hash=hash_password("another-correct-password-77"), role="admin", is_active=True)
        site = Site(organization_id=org.id, name="Other site")
        db.add_all([other_user, site]); db.commit(); other_site_id = site.id
    response = client.post("/api/v1/devices", headers=auth_headers, json={"name": "Bad reference", "device_type": "camera", "site_id": other_site_id})
    assert response.status_code == 404


def test_heartbeat_updates_status(client, auth_headers):
    created = client.post("/api/v1/devices", headers=auth_headers, json={"name": "Sim", "device_type": "simulator"}).json()
    response = client.post(f"/api/v1/devices/{created['id']}/heartbeat", headers=auth_headers, json={"status": "maintenance", "details": {"temperature_c": 32}})
    assert response.status_code == 200
    assert response.json()["status"] == "maintenance"
    assert response.json()["last_seen_at"] is not None
    assert response.json()["details"]["last_heartbeat_details"]["temperature_c"] == 32


def test_duplicate_device_name_rejected(client, auth_headers):
    body = {"name": "Same Device", "device_type": "camera"}
    assert client.post("/api/v1/devices", headers=auth_headers, json=body).status_code == 201
    response = client.post("/api/v1/devices", headers=auth_headers, json=body)
    assert response.status_code == 409


def test_device_not_found(client, auth_headers):
    assert client.get("/api/v1/devices/unknown", headers=auth_headers).status_code == 404


def test_viewer_cannot_mutate_device_heartbeat(client, auth_headers):
    from app.models import User
    from app.core.security import hash_password
    from app.models import Organization
    # User creation is intentionally an admin-only operation.
    created = client.post("/api/v1/users", headers=auth_headers, json={"email": "viewer-hb@example.test", "password": "viewer-heartbeat-pass-77", "role": "viewer"})
    assert created.status_code == 201
    device = client.post("/api/v1/devices", headers=auth_headers, json={"name": "Health test", "device_type": "camera"}).json()
    login = client.post("/api/v1/auth/login", json={"email": "viewer-hb@example.test", "password": "viewer-heartbeat-pass-77"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post(f"/api/v1/devices/{device['id']}/heartbeat", headers=viewer_headers, json={"status": "offline", "details": {}})
    assert response.status_code == 403
