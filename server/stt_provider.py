"""STT (Speech-to-Text) provider abstraction.

Supports:
  - Deepgram: fast cloud STT via REST API
  - Whisper: local fallback (requires openai-whisper)
"""
import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class STTProvider(ABC):
    """Base class for speech-to-text providers."""

    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        encoding: str = "linear16",
        language: str = "en",
    ) -> str:
        """Transcribe raw audio bytes to text."""


class DeepgramSTT(STTProvider):
    """Deepgram REST API for speech-to-text."""

    URL = "https://api.deepgram.com/v1/listen"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("DEEPGRAM_API_KEY is required for DeepgramSTT")
        self.api_key = api_key

    async def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        encoding: str = "linear16",
        language: str = "en",
    ) -> str:
        import httpx

        params = {
            "model": "nova-2",
            "language": language,
            "smart_format": "true",
            "encoding": encoding,
            "sample_rate": str(sample_rate),
        }

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/octet-stream",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.URL,
                params=params,
                headers=headers,
                content=audio_bytes,
            )
            resp.raise_for_status()
            data = resp.json()

        # Extract transcript from Deepgram response
        try:
            transcript = (
                data["results"]["channels"][0]["alternatives"][0]["transcript"]
            )
        except (KeyError, IndexError):
            log.warning("Deepgram response missing transcript: %s", data)
            transcript = ""

        return transcript.strip()


class WhisperSTT(STTProvider):
    """Local Whisper model for speech-to-text (fallback).

    Requires `openai-whisper` package.
    Runs synchronously — wraps in executor for async usage.
    """

    def __init__(self, model_name: str = "base"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            import whisper  # type: ignore

            log.info("Loading Whisper model '%s'...", self.model_name)
            self._model = whisper.load_model(self.model_name)
        return self._model

    async def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        encoding: str = "linear16",
        language: str = "en",
    ) -> str:
        import asyncio
        import tempfile
        import os

        # Write audio to temp file (Whisper needs a file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # Write minimal WAV header + PCM data
            import struct

            num_samples = len(audio_bytes) // 2  # 16-bit samples
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + len(audio_bytes)))
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write(struct.pack("<I", 16))  # chunk size
            f.write(struct.pack("<H", 1))  # PCM format
            f.write(struct.pack("<H", 1))  # mono
            f.write(struct.pack("<I", sample_rate))
            f.write(struct.pack("<I", sample_rate * 2))  # byte rate
            f.write(struct.pack("<H", 2))  # block align
            f.write(struct.pack("<H", 16))  # bits per sample
            f.write(b"data")
            f.write(struct.pack("<I", len(audio_bytes)))
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            loop = asyncio.get_event_loop()
            model = self._load_model()
            result = await loop.run_in_executor(
                None, lambda: model.transcribe(tmp_path, language=language)
            )
            return result.get("text", "").strip()
        finally:
            os.unlink(tmp_path)


def create_stt_provider(provider: str = "deepgram", **kwargs) -> STTProvider:
    """Factory function to create the configured STT provider."""
    if provider == "deepgram":
        return DeepgramSTT(api_key=kwargs.get("api_key", ""))
    elif provider == "whisper":
        return WhisperSTT(model_name=kwargs.get("model_name", "base"))
    else:
        raise ValueError(f"Unknown STT provider: {provider}")
