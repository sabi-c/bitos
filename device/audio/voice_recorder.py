"""VAD-based voice recorder using SharedAudioStream.

Records audio from the shared mic stream with automatic endpoint detection
via WebRTC VAD. Returns WAV bytes when speech ends (2s silence) or timeout.

States: IDLE -> RECORDING -> PROCESSING
"""

from __future__ import annotations

import io
import logging
import struct
import threading
import time
import wave
from collections import deque
from enum import Enum, auto
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_SIZE = 512  # Must match SharedAudioStream default


class RecorderState(Enum):
    IDLE = auto()
    RECORDING = auto()
    PROCESSING = auto()


class VoiceRecorder:
    """VAD-gated voice recorder that consumes frames from SharedAudioStream.

    Usage:
        recorder = VoiceRecorder(shared_stream)
        recorder.start()
        # ... wait for on_done callback or poll is_done ...
        wav_bytes = recorder.get_result()
    """

    SILENCE_TIMEOUT_S = 2.0       # seconds of silence to auto-stop
    MAX_RECORDING_S = 30.0        # hard limit
    MIN_SPEECH_FRAMES = 5         # minimum frames with speech to be valid

    def __init__(
        self,
        shared_stream,
        on_amplitude: Callable[[float], None] | None = None,
        on_done: Callable[[bytes | None], None] | None = None,
        silence_timeout: float = 2.0,
        max_duration: float = 30.0,
    ):
        self._stream = shared_stream
        self._on_amplitude = on_amplitude
        self._on_done = on_done
        self.SILENCE_TIMEOUT_S = silence_timeout
        self.MAX_RECORDING_S = max_duration

        self.state = RecorderState.IDLE
        self._frames: list[np.ndarray] = []
        self._speech_frame_count = 0
        self._silence_start: float | None = None
        self._record_start: float = 0.0
        self._result: bytes | None = None
        self._consumer_buf: deque | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._force_send = threading.Event()
        self._lock = threading.Lock()
        self._rms: float = 0.0

    @property
    def rms(self) -> float:
        """Current RMS amplitude (0.0-1.0), updated each frame."""
        return self._rms

    @property
    def is_done(self) -> bool:
        return self.state in (RecorderState.IDLE,) and self._result is not None

    def start(self) -> bool:
        """Begin recording. Returns False if stream unavailable."""
        if self.state != RecorderState.IDLE:
            return False

        self._frames = []
        self._speech_frame_count = 0
        self._silence_start = None
        self._result = None
        self._stop_event.clear()
        self._force_send.clear()

        # Register as consumer on the shared stream
        self._consumer_buf = self._stream.register("voice_recorder", maxlen=200)
        if not self._stream.is_running:
            self._stream.start()

        self.state = RecorderState.RECORDING
        self._record_start = time.monotonic()
        self._thread = threading.Thread(
            target=self._record_loop, daemon=True, name="voice-recorder"
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """Cancel recording, discard audio."""
        self._stop_event.set()
        self._cleanup()
        self.state = RecorderState.IDLE

    def force_send(self) -> None:
        """Force-finish recording now (skip waiting for silence)."""
        self._force_send.set()

    def get_result(self) -> bytes | None:
        """Return WAV bytes after recording completes. None if cancelled/empty."""
        return self._result

    def _record_loop(self) -> None:
        """Main recording thread: consume frames, run VAD, detect endpoint."""
        from audio.vad import VoiceActivityDetector

        vad = VoiceActivityDetector(aggressiveness=2, sample_rate=SAMPLE_RATE)
        buf = self._consumer_buf

        try:
            while not self._stop_event.is_set():
                now = time.monotonic()
                elapsed = now - self._record_start

                # Hard timeout
                if elapsed >= self.MAX_RECORDING_S:
                    logger.info("voice_recorder: max duration reached (%.0fs)", elapsed)
                    break

                # Force send
                if self._force_send.is_set():
                    logger.info("voice_recorder: force send after %.1fs", elapsed)
                    break

                # Read available frames from consumer buffer
                if not buf:
                    time.sleep(0.01)
                    continue

                frames_read = 0
                while buf and frames_read < 20:  # process up to 20 frames per cycle
                    try:
                        frame = buf.popleft()
                    except IndexError:
                        break
                    frames_read += 1
                    self._frames.append(frame)

                    # Calculate RMS for amplitude feedback
                    rms_raw = np.sqrt(np.mean(frame.astype(np.float32) ** 2))
                    # Normalize to 0-1 range (int16 max is 32767)
                    self._rms = min(1.0, rms_raw / 8000.0)
                    if self._on_amplitude:
                        try:
                            self._on_amplitude(self._rms)
                        except Exception:
                            pass

                    # VAD check
                    is_speech = vad.is_speech(frame)
                    if is_speech:
                        self._speech_frame_count += 1
                        self._silence_start = None
                    else:
                        if self._silence_start is None:
                            self._silence_start = now

                # Check silence timeout (only after we've seen some speech)
                if (
                    self._silence_start is not None
                    and self._speech_frame_count >= self.MIN_SPEECH_FRAMES
                    and (now - self._silence_start) >= self.SILENCE_TIMEOUT_S
                ):
                    logger.info(
                        "voice_recorder: silence endpoint after %.1fs, %d speech frames",
                        elapsed,
                        self._speech_frame_count,
                    )
                    break

                if frames_read == 0:
                    time.sleep(0.01)

            # Done recording
            self.state = RecorderState.PROCESSING
            self._rms = 0.0

            if self._stop_event.is_set():
                # Cancelled
                self._result = None
            elif self._speech_frame_count < self.MIN_SPEECH_FRAMES:
                logger.info("voice_recorder: too few speech frames (%d)", self._speech_frame_count)
                self._result = None
            else:
                self._result = self._frames_to_wav()

            self._cleanup()
            self.state = RecorderState.IDLE

            if self._on_done:
                try:
                    self._on_done(self._result)
                except Exception as exc:
                    logger.error("voice_recorder: on_done callback failed: %s", exc)

        except Exception as exc:
            logger.error("voice_recorder: record loop failed: %s", exc, exc_info=True)
            self._result = None
            self._cleanup()
            self.state = RecorderState.IDLE
            if self._on_done:
                try:
                    self._on_done(None)
                except Exception:
                    pass

    def _frames_to_wav(self) -> bytes:
        """Convert collected frames to WAV bytes."""
        audio = np.concatenate(self._frames)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.astype(np.int16).tobytes())
        return buf.getvalue()

    def _cleanup(self) -> None:
        """Unregister from shared stream."""
        if self._consumer_buf is not None:
            try:
                self._stream.unregister("voice_recorder")
            except Exception:
                pass
            self._consumer_buf = None
