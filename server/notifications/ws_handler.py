"""WebSocket handler for pushing notification events to connected devices."""
from __future__ import annotations

import json
import logging
from typing import Any

from .dispatcher import NotificationDispatcher
from .models import NotificationEvent

logger = logging.getLogger(__name__)


class DeviceWSHandler:
    """Manages WebSocket connections from BITOS devices and broadcasts notification events."""

    def __init__(self, dispatcher: NotificationDispatcher):
        self._dispatcher = dispatcher
        self._store = dispatcher._store
        # device_id -> websocket
        self._devices: dict[str, Any] = {}
        # Register ourselves as a dispatcher callback
        dispatcher.register_callback(self._on_event)

    # ------------------------------------------------------------------
    def register(self, ws: Any, device_id: str) -> None:
        """Track a newly connected device WebSocket."""
        self._devices[device_id] = ws
        logger.info("Device registered: %s (%d total)", device_id, len(self._devices))

    def unregister(self, device_id: str) -> None:
        """Remove a device from the active set."""
        self._devices.pop(device_id, None)
        logger.info("Device unregistered: %s (%d remaining)", device_id, len(self._devices))

    # ------------------------------------------------------------------
    def _on_event(self, event: NotificationEvent) -> None:
        """Dispatcher callback — broadcast new events to all devices."""
        self.broadcast(event.to_dict())

    # ------------------------------------------------------------------
    def broadcast(self, event_dict: dict) -> None:
        """Send an event dict to all connected devices, pruning dead connections."""
        dead: list[str] = []
        for device_id, ws in self._devices.items():
            try:
                ws.send_json(event_dict)
            except Exception:
                logger.warning("Dead connection for device %s, removing", device_id)
                dead.append(device_id)
        for device_id in dead:
            self._devices.pop(device_id, None)

    # ------------------------------------------------------------------
    def handle_message(self, data: dict) -> None:
        """Process an inbound message from a device.

        Supported message types:
        - {"type": "ack", "event_id": "..."} — mark event delivered
        - {"type": "dnd", "enabled": true/false} — log DND state change
        """
        msg_type = data.get("type")
        if msg_type == "ack":
            event_id = data.get("event_id", "")
            if event_id:
                self._store.mark_delivered(event_id)
                logger.info("Event %s acknowledged by device", event_id)
        elif msg_type == "dnd":
            enabled = data.get("enabled", False)
            logger.info("Device DND mode: %s", "enabled" if enabled else "disabled")
        else:
            logger.debug("Unknown device message type: %s", msg_type)

    # ------------------------------------------------------------------
    def handle_reconnect(self, ws: Any, last_event_id: str | None = None, last_ts: float = 0.0) -> None:
        """Replay missed events to a reconnecting device.

        Uses store.get_since() to find events newer than last_ts.
        """
        missed = self._store.get_since(last_ts)
        for event in missed:
            try:
                ws.send_json(event.to_dict())
            except Exception:
                logger.warning("Failed to replay event %s during reconnect", event.id)
                break
