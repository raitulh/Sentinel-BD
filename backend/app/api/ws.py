from __future__ import annotations

import json
import logging
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.security import decode_access_token
from app.core.ws_manager import ws_manager
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/alerts")
async def websocket_alerts_endpoint(websocket: WebSocket) -> None:
    """Real-time incident alert stream over WebSocket.
    
    Requires JWT query token: /api/v1/ws/alerts?token=<jwt>
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token parameter")
        return

    settings = websocket.app.state.settings
    claims = decode_access_token(token, settings.secret_key)
    if claims is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired authentication token")
        return

    user_id = claims.get("sub")
    session_factory = websocket.app.state.session_factory

    with session_factory() as db:
        user = db.scalar(select(User).where(User.id == user_id, User.is_active == True))  # noqa: E712
        if user is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found or account is deactivated")
            return
        org_id = user.organization_id

    await ws_manager.connect(org_id, websocket)
    try:
        # Initial greeting and stream confirmation
        await websocket.send_text(json.dumps({
            "type": "CONNECTION_ESTABLISHED",
            "organization_id": org_id,
            "user_id": user_id,
            "message": "Connected to Sentinel BD real-time threat alert stream."
        }))

        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                if msg.get("type") == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG", "timestamp": msg.get("timestamp")}))
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(org_id, websocket)
    except Exception as exc:
        logger.debug("WebSocket error: %s", exc)
        ws_manager.disconnect(org_id, websocket)
