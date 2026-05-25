"""
WebSocket connection manager for real-time agent/workflow events.
"""
import json
from typing import Dict, List, Set
from fastapi import WebSocket
import structlog

log = structlog.get_logger()


class ConnectionManager:
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}  # workflow_id → sockets
        self._global: List[WebSocket] = []  # subscribed to all events

    async def connect(self, websocket: WebSocket, workflow_id: str = "global"):
        await websocket.accept()
        if workflow_id == "global":
            self._global.append(websocket)
        else:
            if workflow_id not in self._connections:
                self._connections[workflow_id] = set()
            self._connections[workflow_id].add(websocket)
        log.info("ws.connected", workflow_id=workflow_id, total=self.total_connections)

    async def disconnect(self, websocket: WebSocket, workflow_id: str = "global"):
        if workflow_id == "global":
            if websocket in self._global:
                self._global.remove(websocket)
        else:
            if workflow_id in self._connections:
                self._connections[workflow_id].discard(websocket)
        log.info("ws.disconnected", workflow_id=workflow_id)

    async def broadcast(self, message: dict, workflow_id: str = None):
        """Broadcast to all global subscribers and optionally to specific workflow subscribers."""
        data = json.dumps(message, default=str)
        dead_global = []
        for ws in list(self._global):
            try:
                await ws.send_text(data)
            except Exception:
                dead_global.append(ws)
        for ws in dead_global:
            self._global.remove(ws)

        if workflow_id and workflow_id in self._connections:
            dead = []
            for ws in list(self._connections[workflow_id]):
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections[workflow_id].discard(ws)

    @property
    def total_connections(self) -> int:
        wf_conns = sum(len(v) for v in self._connections.values())
        return len(self._global) + wf_conns


manager = ConnectionManager()
