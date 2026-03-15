"""Voice pipeline: record -> transcribe -> AI -> speak.

STATUS: Currently unused. ChatPanel uses audio_pipeline.record()/transcribe()/speak()
directly rather than this higher-level pipeline. Kept for potential future use as a
standalone voice-in/voice-out loop (e.g., fob device or hands-free mode).
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from device.audio.recorder import AudioRecorder
from device.audio.speaker import Speaker
from device.audio.transcriber import WhisperTranscriber

logger = logging.getLogger(__name__)


class VoicePipeline:
    def __init__(
        self,
        openai_key: str,
        ai_send_fn: Callable[[str], str],
        voice_model: str = "assets/voices/en_US-ryan-low.onnx",
    ) -> None:
        self._recorder = AudioRecorder()
        self._transcriber = WhisperTranscriber(openai_key)
        self._speaker = Speaker(voice_model=voice_model)
        self._ai_send_fn = ai_send_fn
        self._state = "idle"
        self._callbacks: list[Callable[[str], None]] = []
        self._worker: Optional[threading.Thread] = None

    @property
    def state(self) -> str:
        return self._state

    def _set_state(self, state: str) -> None:
        self._state = state
        for cb in list(self._callbacks):
            try:
                cb(state)
            except Exception:
                logger.exception("voice_pipeline_state_callback_failed")

    def on_state_change(self, cb: Callable[[str], None]) -> None:
        self._callbacks.append(cb)

    def start_recording(self) -> None:
        if self._state not in {"idle", "error"}:
            return
        ok = self._recorder.start_recording()
        self._set_state("recording" if ok else "error")

    def stop_and_process(self) -> None:
        if self._state != "recording":
            return
        wav_bytes = self._recorder.stop_recording()
        if not wav_bytes:
            self._set_state("idle")
            return
        self._worker = threading.Thread(target=self._process, args=(wav_bytes,), daemon=True)
        self._worker.start()

    def _process(self, wav_bytes: bytes) -> None:
        try:
            self._set_state("transcribing")
            text = self._transcriber.transcribe(wav_bytes)
            if not text:
                self._set_state("idle")
                return

            self._set_state("thinking")
            response = self._ai_send_fn(text)
            if not response:
                self._set_state("idle")
                return

            self._set_state("speaking")
            self._speaker.speak(response)
            self._set_state("idle")
        except Exception:
            logger.exception("voice_pipeline_process_failed")
            self._set_state("error")

    def cancel(self) -> None:
        try:
            self._recorder.stop_recording()
        except Exception:
            logger.exception("voice_pipeline_cancel_recording_failed")
        self._set_state("idle")
