"""Push-to-talk audio recorder for WM8960-compatible microphones."""

from __future__ import annotations

import io
import logging
import threading
import wave
from typing import Optional

import pyaudio

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024
MIN_FRAMES = 5


class AudioRecorder:
    """Records PCM audio while a hold gesture is active."""

    def __init__(self) -> None:
        self._pa = pyaudio.PyAudio()
        self._device_index = self._find_input_device()
        self._stream: Optional[pyaudio.Stream] = None
        self._frames: list[bytes] = []
        self._recording = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _find_input_device(self) -> Optional[int]:
        fallback = None
        for idx in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(idx)
            name = str(info.get("name", "")).lower()
            max_input = int(info.get("maxInputChannels", 0))
            if max_input <= 0:
                continue
            if fallback is None:
                fallback = idx
            if "wm8960" in name or "seeed" in name:
                logger.info("audio_input_device=%s name=%s", idx, info.get("name"))
                return idx
        if fallback is not None:
            info = self._pa.get_device_info_by_index(fallback)
            logger.warning("wm8960_not_found using_fallback=%s name=%s", fallback, info.get("name"))
        else:
            logger.error("no_input_device_found")
        return fallback

    def start_recording(self) -> bool:
        with self._lock:
            if self._recording:
                return True
            if self._device_index is None:
                return False

            self._frames = []
            self._recording = True
            self._stream = self._pa.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=self._device_index,
                frames_per_buffer=CHUNK_SIZE,
            )
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            return True

    def _read_loop(self) -> None:
        while self._recording and self._stream is not None:
            try:
                chunk = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                self._frames.append(chunk)
            except Exception as exc:
                logger.exception("audio_record_read_failed error=%s", exc)
                break

    def stop_recording(self) -> Optional[bytes]:
        with self._lock:
            self._recording = False
            thread = self._thread
            stream = self._stream
            self._thread = None
            self._stream = None

        if thread is not None:
            thread.join(timeout=1.0)

        if stream is not None:
            try:
                stream.stop_stream()
            finally:
                stream.close()

        if len(self._frames) < MIN_FRAMES:
            logger.info("audio_too_short frames=%s", len(self._frames))
            self._frames = []
            return None

        wav_bytes = self._frames_to_wav(self._frames)
        self._frames = []
        return wav_bytes

    def _frames_to_wav(self, frames: list[bytes]) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(CHANNELS)
            wav.setsampwidth(self._pa.get_sample_size(FORMAT))
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(b"".join(frames))
        return buf.getvalue()

    def cleanup(self) -> None:
        self.stop_recording()
        self._pa.terminate()
