"""
BITOS Audio Pipeline (stub)
Will port from whisplay-ai-chatbot in Phase 5.
"""
import platform


class AudioPipeline:
    """Audio recording, STT, and TTS pipeline.
    
    Phase 1: stub that returns is_available=False on desktop.
    Phase 5: will port pyaudio + Whisper + TTS from whisplay-ai-chatbot.
    """

    def __init__(self):
        self._available = False

    def is_available(self) -> bool:
        """Check if audio hardware is available."""
        return self._available

    def record(self, max_seconds: float = 10.0) -> str:
        """Record audio and return file path."""
        raise NotImplementedError(
            "Audio recording not available in desktop mode. "
            "Use keyboard input in the chat panel."
        )

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file to text via Whisper API."""
        raise NotImplementedError("Audio transcription not available in desktop mode.")

    def speak(self, text: str):
        """Convert text to speech and play."""
        raise NotImplementedError("TTS not available in desktop mode.")
