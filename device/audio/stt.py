"""STT with cloud-first fallback: groq -> openai -> vosk -> google.

Tier 1: Groq Whisper Large v3 Turbo ($0.111/hr, fastest cloud, 216x realtime)
Tier 2: OpenAI Whisper API ($0.006/min, reliable fallback)
Tier 3: Vosk (offline, 40MB model, lower accuracy)
Tier 4: Google SpeechRecognition (free, rate-limited)

Local Whisper (PyTorch) is intentionally excluded — too heavy for 512MB Pi.
"""

from __future__ import annotations

import importlib.util
import logging
import os

logger = logging.getLogger(__name__)


class SpeechToText:
    def __init__(self):
        self._groq_key = os.environ.get("GROQ_API_KEY", "")
        self._openai_key = os.environ.get("OPENAI_API_KEY", "")
        self.engine = self._detect_engine()
        logger.info("stt_engine=%s", self.engine)

    @staticmethod
    def _has_module(name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    def _detect_engine(self) -> str:
        if self._groq_key:
            return "groq"
        if self._openai_key:
            return "openai"
        if self._has_module("vosk"):
            return "vosk"
        if self._has_module("speech_recognition"):
            return "google"
        return "none"

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file, falling through tiers on failure."""
        tiers = [
            ("groq", self._transcribe_groq),
            ("openai", self._transcribe_openai),
            ("vosk", self._transcribe_vosk),
            ("google", self._transcribe_google),
        ]
        # Start from the detected engine's position in the chain
        engine_names = [t[0] for t in tiers]
        start = engine_names.index(self.engine) if self.engine in engine_names else 0

        for name, fn in tiers[start:]:
            try:
                if name == "groq" and not self._groq_key:
                    continue
                if name == "openai" and not self._openai_key:
                    continue
                if name == "vosk" and not self._has_module("vosk"):
                    continue
                if name == "google" and not self._has_module("speech_recognition"):
                    continue

                logger.info("stt_trying engine=%s path=%s", name, audio_path)
                result = fn(audio_path)
                if result:
                    logger.info("stt_success engine=%s text=%s", name, result[:50])
                    return result
            except Exception as exc:
                logger.warning("stt_failed engine=%s error=%s", name, exc)
                continue

        logger.error("stt_all_engines_failed path=%s", audio_path)
        return ""

    def _transcribe_groq(self, audio_path: str) -> str:
        """Groq Whisper — fastest cloud option ($0.111/hr)."""
        import httpx

        with open(audio_path, "rb") as f:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._groq_key}"},
                files={"file": ("audio.wav", f, "audio/wav")},
                data={"model": "whisper-large-v3-turbo", "language": "en"},
                timeout=30,
            )
        resp.raise_for_status()
        return resp.json().get("text", "").strip()

    def _transcribe_openai(self, audio_path: str) -> str:
        """OpenAI Whisper API — reliable fallback."""
        import httpx

        with open(audio_path, "rb") as f:
            resp = httpx.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._openai_key}"},
                files={"file": ("audio.wav", f, "audio/wav")},
                data={"model": "whisper-1", "language": "en"},
                timeout=30,
            )
        resp.raise_for_status()
        return resp.json().get("text", "").strip()

    def _transcribe_vosk(self, audio_path: str) -> str:
        """Vosk offline — works without internet, lower accuracy."""
        import json
        import wave

        from vosk import KaldiRecognizer, Model  # type: ignore

        wf = wave.open(audio_path, "rb")
        model = Model(lang="en-us")
        rec = KaldiRecognizer(model, wf.getframerate())
        text_parts: list[str] = []
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                text_parts.append(json.loads(rec.Result()).get("text", ""))
        text_parts.append(json.loads(rec.FinalResult()).get("text", ""))
        return " ".join(part for part in text_parts if part).strip()

    def _transcribe_google(self, audio_path: str) -> str:
        """Google SpeechRecognition — free but rate-limited."""
        import speech_recognition as sr  # type: ignore

        rec = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio = rec.record(source)
        return rec.recognize_google(audio)
