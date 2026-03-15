"""BITOS BLE pairing watcher that starts ANCS for paired iPhones."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import threading
import time
from typing import Callable, Optional

from .ancs_client import ANCSClient

logger = logging.getLogger(__name__)

_DEVICE_LINE_RE = re.compile(r"Device ([0-9A-F:]{17}) (.+)", re.IGNORECASE)


class PairingManager:
    """Poll paired devices and attach ANCS to an iPhone when available.

    Safe to run on dev machines — degrades gracefully when bluetoothctl
    is missing or Bluetooth hardware is unavailable.
    """

    def __init__(self):
        self._ancs_client: Optional[ANCSClient] = None
        self._iphone_address: Optional[str] = None
        self._on_notif_cb: Optional[Callable[[dict], None]] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._has_bluetoothctl = shutil.which("bluetoothctl") is not None

    def on_notification(self, cb: Callable[[dict], None]) -> None:
        self._on_notif_cb = cb

    def start(self) -> None:
        if os.environ.get("BITOS_BLE") == "mock":
            logger.info("[PairingManager] Skipped (BITOS_BLE=mock)")
            return
        if not self._has_bluetoothctl:
            logger.info("[PairingManager] Skipped (bluetoothctl not found — no BT hardware)")
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch, daemon=True, name="pairing-watcher")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._ancs_client:
            try:
                self._ancs_client.stop()
            except Exception as exc:
                logger.debug("[PairingManager] ANCS stop error: %s", exc)

    def _get_paired_iphone(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["bluetoothctl", "devices", "Paired"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except FileNotFoundError:
            logger.debug("[PairingManager] bluetoothctl not found")
            self._has_bluetoothctl = False
            return None
        except Exception as exc:
            logger.debug("[PairingManager] bluetoothctl check failed: %s", exc)
            return None

        for line in result.stdout.splitlines():
            match = _DEVICE_LINE_RE.match(line)
            if not match:
                continue
            addr, name = match.group(1), match.group(2)
            lowered = name.lower()
            if "iphone" in lowered or "apple" in lowered:
                return addr
        return None

    def _watch(self) -> None:
        logger.info("[PairingManager] Watching for paired iPhone")
        while self._running:
            try:
                if not self._has_bluetoothctl:
                    logger.info("[PairingManager] bluetoothctl disappeared — stopping watcher")
                    break
                addr = self._get_paired_iphone()
                if addr and addr != self._iphone_address:
                    logger.info("[PairingManager] iPhone found: %s — connecting ANCS", addr)
                    self._iphone_address = addr
                    self._start_ancs(addr)
            except Exception as exc:
                logger.error("[PairingManager] Watch loop error: %s", exc)
            time.sleep(10)

    def _start_ancs(self, addr: str) -> None:
        try:
            if self._ancs_client:
                self._ancs_client.stop()
            self._ancs_client = ANCSClient()
            if self._on_notif_cb:
                self._ancs_client.on_notification(self._on_notif_cb)
            self._ancs_client.connect(addr)
        except Exception as exc:
            logger.error("[PairingManager] ANCS connect error for %s: %s", addr, exc)
