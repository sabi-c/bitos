"""STT helpers with runtime fallback chain: whisper -> vosk -> google."""

from __future__ import annotations

import importlib.util
import logging


logger = logging.getLogger(__name__)


class SpeechToText:
    def __init__(self):
        self.engine = self._detect_engine()
        logger.info("stt_engine=%s", self.engine)

    @staticmethod
    def _has_module(name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    def _detect_engine(self) -> str:
        if self._has_module("whisper"):
            return "whisper"
        if self._has_module("vosk"):
            return "vosk"
        if self._has_module("speech_recognition"):
            return "google"
        return "none"

    def transcribe(self, audio_path: str) -> str:
        if self.engine == "whisper":
            return self._transcribe_whisper(audio_path)
        if self.engine == "vosk":
            return self._transcribe_vosk(audio_path)
        if self.engine == "google":
            return self._transcribe_google(audio_path)
        logger.warning("stt_engine=none; returning empty transcript")
        return ""

    def _transcribe_whisper(self, audio_path: str) -> str:
        import whisper  # type: ignore

        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        return str(result.get("text", "")).strip()

    def _transcribe_vosk(self, audio_path: str) -> str:
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
        import speech_recognition as sr  # type: ignore

        rec = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio = rec.record(source)
        return rec.recognize_google(audio)
