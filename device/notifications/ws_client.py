"""WebSocket client for real-time notification delivery from server."""
from __future__ import annotations

import json
import logging
import threading
import time

logger = logging.getLogger(__name__)

MAX_BACKOFF_S = 30

try:
    import websocket  # websocket-client library
except ImportError:
    websocket = None  # type: ignore[assignment]
    logger.warning("websocket-client not installed — DeviceWSClient disabled")


class DeviceWSClient:
    """Persistent WebSocket connection with auto-reconnect and exponential backoff."""

    def __init__(self, url: str, device_id: str = "bitos_main"):
        self._url = url
        self._device_id = device_id
        self._connected = False
        self._last_event_id: str | None = None
        self._attempts = 0
        self._stop_event = threading.Event()
        self._ws: "websocket.WebSocket | None" = None  # type: ignore[name-defined]
        self._thread: threading.Thread | None = None

        # Public callbacks
        self.on_event: "((dict) -> None) | None" = None
        self.on_connect: "(() -> None) | None" = None
        self.on_disconnect: "(() -> None) | None" = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_event_id(self) -> str | None:
        return self._last_event_id

    # ── Public API ────────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn daemon thread running the connection loop."""
        if websocket is None:
            logger.warning("Cannot start DeviceWSClient — websocket-client not installed")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ws-notif")
        self._thread.start()

    def stop(self) -> None:
        """Signal the loop to stop and close the WebSocket."""
        self._stop_event.set()
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
        self._connected = False

    def send_ack(self, event_id: str) -> None:
        """Acknowledge receipt of an event."""
        self._send({"type": "ack", "id": event_id})

    def send_dnd(self, active: bool, reason: str = "") -> None:
        """Toggle do-not-disturb mode on the server."""
        self._send({"type": "dnd", "active": active, "reason": reason})

    # ── Internal ──────────────────────────────────────────────────────

    def _send(self, payload: dict) -> None:
        if self._ws is not None and self._connected:
            try:
                self._ws.send(json.dumps(payload))
            except Exception:
                logger.debug("Failed to send WS message", exc_info=True)

    def _run_loop(self) -> None:
        """Connect, receive messages, reconnect on failure."""
        while not self._stop_event.is_set():
            try:
                self._ws = websocket.WebSocket()  # type: ignore[union-attr]
                self._ws.connect(self._url)
                self._connected = True
                self._attempts = 0

                # On reconnect, request replay of missed events
                if self._last_event_id is not None:
                    self._send({"type": "reconnect", "last_event_id": self._last_event_id})

                if self.on_connect is not None:
                    self.on_connect()

                # Receive loop
                while not self._stop_event.is_set():
                    raw = self._ws.recv()
                    if raw:
                        self._handle_message(raw)

            except Exception:
                logger.debug("WS connection error", exc_info=True)
            finally:
                self._connected = False
                if self._ws is not None:
                    try:
                        self._ws.close()
                    except Exception:
                        pass
                    self._ws = None

                if self.on_disconnect is not None:
                    self.on_disconnect()

            if self._stop_event.is_set():
                break

            # Backoff before reconnect
            delay = self._next_backoff()
            self._stop_event.wait(delay)

    def _handle_message(self, raw: str) -> None:
        """Parse JSON, track last_event_id, fire on_event callback."""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.debug("Ignoring malformed WS message: %s", raw[:100])
            return

        if not isinstance(data, dict):
            logger.debug("Ignoring non-dict WS message")
            return

        # Track event ID for replay on reconnect
        event_id = data.get("id")
        if event_id is not None:
            self._last_event_id = str(event_id)

        if self.on_event is not None:
            self.on_event(data)

    def _next_backoff(self) -> float:
        """Exponential backoff: 1, 2, 4, 8, ... capped at MAX_BACKOFF_S."""
        delay = min(2 ** self._attempts, MAX_BACKOFF_S)
        self._attempts += 1
        return float(delay)
