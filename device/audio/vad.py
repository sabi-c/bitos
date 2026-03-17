"""Voice Activity Detection using WebRTC VAD."""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

try:
    import webrtcvad
    _HAS_VAD = True
except ImportError:
    _HAS_VAD = False
    logger.warning("webrtcvad not available — VAD disabled")


class VoiceActivityDetector:
    """WebRTC VAD wrapper for silence detection and trimming."""

    def __init__(self, aggressiveness: int = 2, sample_rate: int = 16000):
        self._sample_rate = sample_rate
        self._vad = webrtcvad.Vad(aggressiveness) if _HAS_VAD else None

    @property
    def available(self) -> bool:
        return self._vad is not None

    def is_speech(self, frame: np.ndarray) -> bool:
        """Check if a 16-bit PCM frame contains speech.

        WebRTC VAD requires 10/20/30ms frames.
        At 16kHz that is 160/320/480 samples.
        Our standard frame is 512 samples — we use the first 480 (30ms).
        """
        if not self._vad:
            return True  # assume speech if VAD unavailable
        raw = frame.astype(np.int16).tobytes()
        # 480 samples * 2 bytes = 960 bytes for 30ms at 16kHz
        chunk = raw[:960]
        if len(chunk) < 960:
            return True
        try:
            return self._vad.is_speech(chunk, self._sample_rate)
        except Exception:
            return True

    def trim_silence(self, audio: np.ndarray, frame_ms: int = 30) -> np.ndarray:
        """Trim leading and trailing silence from audio array."""
        if not self._vad:
            return audio
        frame_samples = self._sample_rate * frame_ms // 1000
        n_frames = len(audio) // frame_samples

        speech_start = 0
        speech_end = len(audio)

        # Find first speech frame
        for i in range(n_frames):
            chunk = audio[i * frame_samples:(i + 1) * frame_samples]
            if self.is_speech(chunk):
                speech_start = max(0, i * frame_samples - frame_samples)  # keep 1 frame before
                break

        # Find last speech frame
        for i in range(n_frames - 1, -1, -1):
            chunk = audio[i * frame_samples:(i + 1) * frame_samples]
            if self.is_speech(chunk):
                speech_end = min(len(audio), (i + 2) * frame_samples)  # keep 1 frame after
                break

        trimmed = audio[speech_start:speech_end]
        if len(trimmed) < frame_samples:
            return audio  # don't return empty
        return trimmed

    def detect_silence_duration(self, frames_buffer: list[np.ndarray]) -> float:
        """Check how many seconds of trailing silence are in a frame buffer."""
        if not self._vad or not frames_buffer:
            return 0.0
        silence_frames = 0
        for frame in reversed(frames_buffer):
            if self.is_speech(frame):
                break
            silence_frames += 1
        if not frames_buffer:
            return 0.0
        return silence_frames * len(frames_buffer[0]) / self._sample_rate
