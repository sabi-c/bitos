"""Wake-word detector using Porcupine via SharedAudioStream consumer pattern.

Porcupine (pvporcupine) is optional — graceful fallback when not installed.
Enable with BITOS_WAKE_WORD=on environment variable.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from audio.shared_stream import SharedAudioStream

logger = logging.getLogger(__name__)

try:
    import pvporcupine
    _HAS_PORCUPINE = True
except ImportError:
    _HAS_PORCUPINE = False

# Also support legacy openWakeWord as fallback
try:
    from openwakeword.model import Model as OWWModel
    _HAS_OWW = True
except ImportError:
    _HAS_OWW = False


class WakeWordDetector:
    """
    Hands-free "Hey Bitos" trigger using SharedAudioStream consumer pattern.
    Disabled by default (BITOS_WAKE_WORD=off).
    Prefers Porcupine, falls back to openWakeWord, then to disabled.
    """

    ENABLED = os.environ.get("BITOS_WAKE_WORD", "off") == "on"
    CONSUMER_NAME = "wake_word"

    def __init__(self, shared_stream: SharedAudioStream | None = None) -> None:
        self._shared_stream = shared_stream
        self._buf: deque | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._porcupine = None

    def start(self, on_detected: Callable) -> None:
        if not self.ENABLED:
            return

        if not _HAS_PORCUPINE and not _HAS_OWW:
            logger.warning("No wake word engine available (install pvporcupine or openwakeword)")
            return

        if self._thread and self._thread.is_alive():
            return

        self._stop.clear()

        # Register as SharedAudioStream consumer if available
        if self._shared_stream is not None:
            self._buf = self._shared_stream.register(self.CONSUMER_NAME, maxlen=200)

        if _HAS_PORCUPINE:
            self._thread = threading.Thread(
                target=self._porcupine_loop,
                args=(on_detected,),
                name="wake-word-porcupine",
                daemon=True,
            )
        else:
            self._thread = threading.Thread(
                target=self._oww_loop,
                args=(on_detected,),
                name="wake-word-oww",
                daemon=True,
            )
        self._thread.start()

    def _porcupine_loop(self, on_detected: Callable) -> None:
        """Process audio frames from SharedAudioStream through Porcupine."""
        access_key = os.environ.get("PORCUPINE_ACCESS_KEY", "")
        keyword_path = os.environ.get("PORCUPINE_KEYWORD_PATH")
        sensitivity = float(os.environ.get("BITOS_WAKE_WORD_SENSITIVITY", "0.5"))

        try:
            kw_args = {}
            if keyword_path and os.path.exists(keyword_path):
                kw_args["keyword_paths"] = [keyword_path]
                kw_args["sensitivities"] = [sensitivity]
            else:
                # Fall back to built-in "porcupine" keyword for testing
                kw_args["keywords"] = ["porcupine"]
                kw_args["sensitivities"] = [sensitivity]
                logger.info("[WakeWord] No custom keyword, using built-in 'porcupine'")

            self._porcupine = pvporcupine.create(
                access_key=access_key,
                **kw_args,
            )
            logger.info(
                "[WakeWord] Porcupine ready: frame_length=%d, sample_rate=%d",
                self._porcupine.frame_length,
                self._porcupine.sample_rate,
            )
        except Exception as exc:
            logger.error("[WakeWord] Porcupine init failed: %s", exc)
            return

        try:
            while not self._stop.is_set():
                frame = self._get_frame()
                if frame is None:
                    time.sleep(0.01)
                    continue

                try:
                    keyword_index = self._porcupine.process(frame[:self._porcupine.frame_length])
                    if keyword_index >= 0:
                        logger.info("[WakeWord] Detected! keyword_index=%d", keyword_index)
                        on_detected()
                except Exception as exc:
                    logger.warning("[WakeWord] Process error: %s", exc)
        finally:
            if self._porcupine:
                self._porcupine.delete()
                self._porcupine = None

    def _oww_loop(self, on_detected: Callable) -> None:
        """Legacy openWakeWord fallback loop."""
        try:
            model = OWWModel()
        except Exception as exc:
            logger.error("[WakeWord] openWakeWord init failed: %s", exc)
            return

        while not self._stop.is_set():
            frame = self._get_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            # openWakeWord integration point — threshold check would go here
            _ = model
            time.sleep(0.01)

    def _get_frame(self):
        """Get next audio frame from shared stream buffer."""
        if self._buf is not None:
            try:
                return self._buf.popleft()
            except IndexError:
                return None
        return None

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        # Unregister from shared stream
        if self._shared_stream is not None:
            self._shared_stream.unregister(self.CONSUMER_NAME)
            self._buf = None
