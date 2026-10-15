from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections grouped by organization ID."""

    def __init__(self) -> None:
        # Maps organization_id -> set of active WebSocket instances
        self._active_connections: dict[str, set[WebSocket]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, organization_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if organization_id not in self._active_connections:
            self._active_connections[organization_id] = set()
        self._active_connections[organization_id].add(websocket)
        logger.info("WebSocket client connected to org: %s (total: %d)", organization_id, len(self._active_connections[organization_id]))

    def disconnect(self, organization_id: str, websocket: WebSocket) -> None:
        if organization_id in self._active_connections:
            self._active_connections[organization_id].discard(websocket)
            if not self._active_connections[organization_id]:
                del self._active_connections[organization_id]
        logger.info("WebSocket client disconnected from org: %s", organization_id)

    async def broadcast_to_org(self, organization_id: str, payload: dict[str, Any]) -> None:
        """Asynchronously send payload to all clients connected for the given organization."""
        connections = self._active_connections.get(organization_id, set())
        if not connections:
            return

        message = json.dumps(payload)
        stale: list[WebSocket] = []
        for connection in list(connections):
            try:
                await connection.send_text(message)
            except Exception as exc:
                logger.debug("Failed sending to WebSocket, marking for removal: %s", exc)
                stale.append(connection)

        for conn in stale:
            self.disconnect(organization_id, conn)

    def broadcast_threadsafe(self, organization_id: str, payload: dict[str, Any]) -> None:
        """Thread-safe broadcast callable from background worker threads."""
        connections = self._active_connections.get(organization_id, set())
        if not connections:
            return

        target_loop = self._loop
        if target_loop is None:
            try:
                target_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

        if target_loop and target_loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast_to_org(organization_id, payload), target_loop)
        else:
            logger.debug("No active event loop available to broadcast WebSocket message.")


ws_manager = ConnectionManager()
