"""OpenAI Whisper transcription helper."""

from __future__ import annotations

import io
import logging
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    def __init__(self, api_key: str) -> None:
        self._client = OpenAI(api_key=api_key) if api_key else None

    def transcribe(self, wav_bytes: bytes) -> Optional[str]:
        if not self._client or not wav_bytes:
            return None
        try:
            audio_file = io.BytesIO(wav_bytes)
            audio_file.name = "speech.wav"
            result = self._client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en",
            )
            text = (getattr(result, "text", "") or "").strip()
            if text:
                logger.info("transcribed_text=%s", text)
                return text
        except Exception as exc:
            logger.exception("transcription_failed error=%s", exc)
        return None
