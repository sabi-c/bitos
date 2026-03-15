"""BITOS Battery Monitor.

Reads PiSugar battery state from the local ``pisugar-server`` UNIX socket.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from typing import Optional


logger = logging.getLogger(__name__)

PISUGAR_SOCKET = "/tmp/pisugar-server.sock"
POLL_INTERVAL_S = 30


class BatteryMonitor:
    """Poll battery data from pisugar-server in a background thread."""

    def __init__(self, poll_interval_s: int = POLL_INTERVAL_S):
        self.level: Optional[int] = None
        self.charging: bool = False
        self.plugged: bool = False
        self.model: str = "unknown"

        self._poll_interval = max(5, int(poll_interval_s))
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="battery-monitor")
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def get_status(self) -> dict:
        """Return a compatibility status payload for current callers."""
        with self._lock:
            pct = 0 if self.level is None else int(self.level)
            status = {
                "pct": pct,
                "percentage": pct,
                "charging": bool(self.charging),
                "plugged": bool(self.plugged),
                "present": self.level is not None,
                "model": self.model,
            }
        return status

    def _query(self, command: str) -> Optional[str]:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect(PISUGAR_SOCKET)
                s.sendall((command + "\n").encode("utf-8"))
                response = s.recv(256).decode("utf-8", errors="ignore").strip()
            if ":" in response:
                return response.split(":", 1)[1].strip()
            return response or None
        except (FileNotFoundError, ConnectionRefusedError, TimeoutError):
            logger.debug("pisugar-server unavailable for command=%s", command)
            return None
        except Exception as exc:
            logger.debug("pisugar query failed command=%s error=%s", command, exc)
            return None

    def _run(self) -> None:
        model = self._query("get model")
        if model:
            with self._lock:
                self.model = model
            logger.info("PiSugar model=%s", model)

        self._poll()
        while self._running:
            time.sleep(self._poll_interval)
            if not self._running:
                break
            self._poll()

    def _poll(self) -> None:
        battery_resp = self._query("get battery")
        plugged_resp = self._query("battery_power_plugged")
        charging_resp = self._query("battery_allow_charging")

        with self._lock:
            if battery_resp:
                try:
                    self.level = max(0, min(100, round(float(battery_resp))))
                except ValueError:
                    logger.debug("invalid battery response=%r", battery_resp)

            if plugged_resp:
                self.plugged = plugged_resp.lower() == "true"

            if charging_resp:
                self.charging = charging_resp.lower() == "true" and self.plugged
            else:
                self.charging = self.plugged

        logger.debug("battery_update status=%s", self.get_status())

    def configure_safe_shutdown(self, threshold_pct: int = 5, delay_s: int = 30) -> None:
        threshold = max(1, min(50, int(threshold_pct)))
        delay = max(0, int(delay_s))
        self._query(f"safe_shutdown_level {threshold}")
        self._query(f"safe_shutdown_delay {delay}")
        logger.info("pisugar safe shutdown configured threshold=%s delay=%s", threshold, delay)

    def get_status_text(self) -> str:
        with self._lock:
            if self.level is None:
                return "??%"
            icon = "⚡" if self.charging else ("🔌" if self.plugged else "🔋")
            return f"{icon}{self.level}%"

    def is_low(self, threshold: int = 15) -> bool:
        with self._lock:
            return self.level is not None and self.level <= threshold
