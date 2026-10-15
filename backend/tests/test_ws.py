from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient


def test_websocket_requires_valid_token(client: TestClient):
    # Without token: should disconnect/close
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/ws/alerts") as ws:
            ws.receive_json()

    # With invalid token: should disconnect/close
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/ws/alerts?token=invalid.jwt.token") as ws:
            ws.receive_json()


def test_websocket_connects_and_pongs(client: TestClient, auth_headers):
    token = auth_headers["Authorization"].replace("Bearer ", "")
    with client.websocket_connect(f"/api/v1/ws/alerts?token={token}") as ws:
        init_msg = ws.receive_json()
        assert init_msg["type"] == "CONNECTION_ESTABLISHED"
        assert "organization_id" in init_msg

        # Ping test
        ws.send_json({"type": "PING", "timestamp": 1700000000})
        pong_msg = ws.receive_json()
        assert pong_msg["type"] == "PONG"
        assert pong_msg["timestamp"] == 1700000000


def test_websocket_receives_event_broadcast(client: TestClient, auth_headers):
    token = auth_headers["Authorization"].replace("Bearer ", "")
    with client.websocket_connect(f"/api/v1/ws/alerts?token={token}") as ws:
        init_msg = ws.receive_json()
        assert init_msg["type"] == "CONNECTION_ESTABLISHED"

        # Create an event via API
        event_body = {
            "source_id": "test-cam-09",
            "event_type": "motion_observed",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "score": 0.92,
            "score_kind": "foreground_pixel_ratio",
            "details": {
                "primary_label": "person",
                "semantic_classification": True,
            }
        }
        resp = client.post("/api/v1/events", headers=auth_headers, json=event_body)
        assert resp.status_code == 201

        # The WebSocket client should receive NEW_ALERT!
        alert_msg = ws.receive_json()
        assert alert_msg["type"] == "NEW_ALERT"
        assert alert_msg["event"]["source_id"] == "test-cam-09"
        assert alert_msg["event"]["primary_label"] == "person"
        assert alert_msg["event"]["is_semantic"] is True
