"""BITOS BLE pairing watcher that starts ANCS for paired iPhones."""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from typing import Callable, Optional

from .ancs_client import ANCSClient

logger = logging.getLogger(__name__)

_DEVICE_LINE_RE = re.compile(r"Device ([0-9A-F:]{17}) (.+)", re.IGNORECASE)


class PairingManager:
    """Poll paired devices and attach ANCS to an iPhone when available."""

    def __init__(self):
        self._ancs_client: Optional[ANCSClient] = None
        self._iphone_address: Optional[str] = None
        self._on_notif_cb: Optional[Callable[[dict], None]] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def on_notification(self, cb: Callable[[dict], None]) -> None:
        self._on_notif_cb = cb

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._watch, daemon=True, name="pairing-watcher")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._ancs_client:
            self._ancs_client.stop()

    def _get_paired_iphone(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["bluetoothctl", "devices", "Paired"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception as exc:
            logger.debug("Pairing manager bluetoothctl check failed: %s", exc)
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
        logger.info("Pairing manager watching for paired iPhone")
        while self._running:
            addr = self._get_paired_iphone()
            if addr and addr != self._iphone_address:
                logger.info("iPhone found: %s — connecting ANCS", addr)
                self._iphone_address = addr
                self._start_ancs(addr)
            time.sleep(10)

    def _start_ancs(self, addr: str) -> None:
        if self._ancs_client:
            self._ancs_client.stop()
        self._ancs_client = ANCSClient()
        if self._on_notif_cb:
            self._ancs_client.on_notification(self._on_notif_cb)
        self._ancs_client.connect(addr)
