"""Device status characteristic with read + notify behavior."""
from __future__ import annotations

import json
import threading
from typing import Callable


class DeviceStatusCharacteristic:
    """Unprotected device status characteristic payload store + notifier."""

    def __init__(self):
        self._status = {
            "battery_pct": 0,
            "charging": False,
            "wifi_connected": False,
            "wifi_ssid": "",
            "ai_online": False,
            "active_screen": "unknown",
            "agent_mode": "normal",
            "bitos_version": "1.0.0",
            "uptime_seconds": 0,
        }
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_notified: bytes = b""

    def ReadValue(self, _options) -> bytes:
        with self._lock:
            return json.dumps(self._status).encode("utf-8")

    def update_and_notify(self, status: dict) -> None:
        with self._lock:
            merged = dict(self._status)
            merged.update(status)
            self._status = merged
            self._last_notified = json.dumps(self._status).encode("utf-8")

    def start_periodic_updates(self, get_status_fn: Callable, interval_s: int = 30) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()

        def _loop():
            while not self._stop.wait(max(1, int(interval_s))):
                status = get_status_fn()
                if isinstance(status, dict):
                    self.update_and_notify(status)

        self._thread = threading.Thread(target=_loop, name="device-status-char", daemon=True)
        self._thread.start()

    def stop_periodic_updates(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
