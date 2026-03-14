"""
BITOS Audio Pipeline (stub)
Will port from whisplay-ai-chatbot in Phase 5.
"""
import logging
import os


logger = logging.getLogger(__name__)


_AUDIO_MODE_MOCK = "mock"
_AUDIO_MODE_HW = "hw:0"


class AudioPipeline:
    """Audio recording, STT, and TTS pipeline.
    
    Phase 1: stub that returns is_available=False on desktop.
    Phase 5: will port pyaudio + Whisper + TTS from whisplay-ai-chatbot.
    """

    def __init__(self):
        self._mode = os.environ.get("BITOS_AUDIO", _AUDIO_MODE_MOCK).lower()
        self._available = self._mode == _AUDIO_MODE_HW
        if self._mode == _AUDIO_MODE_MOCK:
            logger.info("[BITOS] Audio pipeline initialized in mock mode")
        elif self._mode == _AUDIO_MODE_HW:
            logger.info("[BITOS] Audio pipeline initialized in hardware mode (%s)", self._mode)
        else:
            logger.warning("[BITOS] Unknown BITOS_AUDIO mode '%s'; falling back to mock mode", self._mode)
            self._mode = _AUDIO_MODE_MOCK
            self._available = False

    def _is_mock_mode(self) -> bool:
        return self._mode == _AUDIO_MODE_MOCK

    def is_available(self) -> bool:
        """Check if audio hardware is available."""
        return self._available

    def record(self, max_seconds: float = 10.0) -> str:
        """Record audio and return file path."""
        if self._is_mock_mode():
            logger.info("[BITOS] Audio mock record invoked (max_seconds=%s)", max_seconds)
            return ""
        raise NotImplementedError(
            "Audio recording not available in desktop mode. "
            "Use keyboard input in the chat panel."
        )

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file to text via Whisper API."""
        if self._is_mock_mode():
            logger.info("[BITOS] Audio mock transcribe invoked (audio_path=%s)", audio_path)
            return ""
        raise NotImplementedError("Audio transcription not available in desktop mode.")

    def speak(self, text: str):
        """Convert text to speech and play."""
        if self._is_mock_mode():
            logger.info("[BITOS] Audio mock speak invoked (text_len=%s)", len(text))
            return
        raise NotImplementedError("TTS not available in desktop mode.")
