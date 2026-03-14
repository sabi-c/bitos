"""
BITOS Audio Pipeline (stub)
Will port from whisplay-ai-chatbot in Phase 5.
"""
import os
import tempfile


class AudioPipeline:
    """Audio recording, STT, and TTS pipeline.
    
    Phase 1: stub that returns is_available=False on desktop.
    Phase 5: will port pyaudio + Whisper + TTS from whisplay-ai-chatbot.
    """

    def __init__(self):
        self._available = os.environ.get("BITOS_AUDIO", "").lower() == "mock"
        self._last_text = ""

    def is_available(self) -> bool:
        """Check if audio hardware is available."""
        return self._available

    def record(self, max_seconds: float = 10.0) -> str:
        """Record audio and return file path."""
        if not self._available:
            raise NotImplementedError(
                "Audio recording not available in desktop mode. "
                "Use keyboard input in the chat panel."
            )

        _ = max_seconds
        typed = input("TYPE MESSAGE: ").strip()
        self._last_text = typed
        with tempfile.NamedTemporaryFile(prefix="bitos_mock_audio_", suffix=".txt", dir="/tmp", delete=False) as f:
            f.write(typed.encode("utf-8"))
            return f.name

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file to text via Whisper API."""
        if not self._available:
            raise NotImplementedError("Audio transcription not available in desktop mode.")

        try:
            with open(audio_path, "r", encoding="utf-8") as f:
                txt = f.read().strip()
                return txt or self._last_text
        except Exception:
            return self._last_text
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def speak(self, text: str):
        """Convert text to speech and play."""
        raise NotImplementedError("TTS not available in desktop mode.")
