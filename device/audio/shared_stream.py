"""Single microphone stream shared across multiple consumers (wake word, recorder, VAD)."""

from __future__ import annotations

import collections
import logging
import threading
import time

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_SIZE = 512  # Porcupine expects 512 samples per frame
CHANNELS = 1
FORMAT_DTYPE = np.int16

try:
    import pyaudio
    _HAS_PYAUDIO = True
except ImportError:
    _HAS_PYAUDIO = False
    logger.warning("pyaudio not available — SharedAudioStream will use silence generator")


class SharedAudioStream:
    """Opens one audio capture stream, distributes frames to registered consumers."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, frame_size: int = FRAME_SIZE):
        self._sample_rate = sample_rate
        self._frame_size = frame_size
        self._consumers: dict[str, collections.deque] = {}
        self._lock = threading.Lock()
        self._start_lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def register(self, name: str, maxlen: int = 100) -> collections.deque:
        """Register a named consumer. Returns a deque that receives audio frames."""
        with self._lock:
            buf: collections.deque = collections.deque(maxlen=maxlen)
            self._consumers[name] = buf
            logger.info("[SharedAudio] Registered consumer: %s", name)
            return buf

    def unregister(self, name: str) -> None:
        with self._lock:
            self._consumers.pop(name, None)
            logger.info("[SharedAudio] Unregistered consumer: %s", name)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def frame_size(self) -> int:
        return self._frame_size

    def start(self) -> None:
        with self._start_lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True, name="shared-audio")
            self._thread.start()

    def stop(self) -> None:
        with self._start_lock:
            self._running = False
            thread = self._thread
            self._thread = None
        if thread:
            thread.join(timeout=2.0)

    def _distribute(self, frame: np.ndarray) -> None:
        """Push a frame to all registered consumer buffers."""
        with self._lock:
            for buf in self._consumers.values():
                buf.append(frame)

    def _read_loop(self) -> None:
        """Read from mic, distribute to all consumers."""
        if not _HAS_PYAUDIO:
            self._silence_loop()
            return

        pa = None
        stream = None
        try:
            pa = pyaudio.PyAudio()
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=self._sample_rate,
                input=True,
                frames_per_buffer=self._frame_size,
            )
            logger.info(
                "[SharedAudio] Mic stream opened: %dHz, %d frame",
                self._sample_rate,
                self._frame_size,
            )
        except Exception as exc:
            logger.error("[SharedAudio] Failed to open mic: %s", exc)
            self._running = False
            if pa:
                pa.terminate()
            return

        try:
            while self._running:
                try:
                    raw = stream.read(self._frame_size, exception_on_overflow=False)
                    frame = np.frombuffer(raw, dtype=FORMAT_DTYPE)
                    self._distribute(frame)
                except IOError as exc:
                    logger.warning("[SharedAudio] Read error: %s", exc)
                    time.sleep(0.01)
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
            logger.info("[SharedAudio] Mic stream closed")

    def _silence_loop(self) -> None:
        """Fallback: generate silent frames when pyaudio is unavailable (dev/test)."""
        logger.info("[SharedAudio] Running silence generator (no pyaudio)")
        silence = np.zeros(self._frame_size, dtype=FORMAT_DTYPE)
        interval = self._frame_size / self._sample_rate
        while self._running:
            self._distribute(silence)
            time.sleep(interval)
