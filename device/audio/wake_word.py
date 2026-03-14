"""Wake-word detector stub for optional openWakeWord integration."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable


logger = logging.getLogger(__name__)


class WakeWordDetector:
    """
    # WHY THIS EXISTS: hands-free "Hey Bitos" trigger.
    # Disabled by default (BITOS_WAKE_WORD=off).
    # When enabled, uses openWakeWord library.
    """

    ENABLED = os.environ.get("BITOS_WAKE_WORD", "off") == "on"

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self, on_detected: Callable) -> None:
        if not self.ENABLED:
            return
        try:
            from openwakeword.model import Model
        except ImportError:
            logger.warning("openwakeword not installed, wake word disabled")
            return

        if self._thread and self._thread.is_alive():
            return

        self._stop.clear()

        def _loop() -> None:
            # Stub loop: wires in model creation without running audio ingestion yet.
            _ = Model()
            while not self._stop.wait(1.0):
                time.sleep(0.01)
                # Future implementation should call on_detected() when model threshold is crossed.

        self._thread = threading.Thread(target=_loop, name="wake-word-detector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
