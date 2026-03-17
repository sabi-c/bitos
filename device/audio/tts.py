"""TTS helpers with runtime fallback chain.

Priority: edge_tts -> speechify -> chatterbox -> piper -> openai -> espeak -> silent.

Edge TTS is preferred when available because it's free, fast (~200ms TTFB),
and requires no API key. Speechify remains the premium option when keyed.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

from .player import AudioPlayer


logger = logging.getLogger(__name__)

SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", os.getenv("ALSA_SAMPLE_RATE", "48000")))
CHANNELS = int(os.getenv("AUDIO_CHANNELS", "2"))
PLAYBACK_DEVICE = os.getenv("ALSA_PLAYBACK_DEVICE", "default")


class TextToSpeech:
    def __init__(self, player: AudioPlayer | None = None):
        self.player = player or AudioPlayer()
        # Apply persisted volume setting
        try:
            from storage.repository import DeviceRepository
            repo = DeviceRepository()
            vol = repo.get_setting("volume", 100)
            self.player.set_volume(max(0, min(100, int(vol))) / 100.0)
        except Exception:
            pass
        # Load voice settings from repository
        self._voice_id = None
        self._voice_params = {}
        try:
            from storage.repository import DeviceRepository
            import json
            _repo = DeviceRepository()
            self._voice_id = _repo.get_setting("voice_id", None)
            params_raw = _repo.get_setting("voice_params", "{}")
            self._voice_params = json.loads(params_raw) if isinstance(params_raw, str) else (params_raw or {})
        except Exception:
            pass
        self.engine = self._detect_engine()
        # Track latency metrics for diagnostics
        self.last_synthesis_ms: int = 0
        self.last_ttfb_ms: int = 0  # time to first audio byte
        logger.info("tts_engine=%s", self.engine)

    @staticmethod
    def _check_cartesia() -> bool:
        """Return True if cartesia SDK is importable and API key is set."""
        try:
            from . import cartesia_provider
            return cartesia_provider.is_available()
        except Exception:
            return False

    @staticmethod
    def _check_edge_tts() -> bool:
        """Return True if edge-tts is importable."""
        try:
            from . import edge_tts_provider
            return edge_tts_provider.is_available()
        except Exception:
            return False

    @staticmethod
    def _check_chatterbox() -> bool:
        """Return True if chatterbox-tts is importable."""
        try:
            import chatterbox.tts  # noqa: F401
            return True
        except Exception:
            return False

    def _detect_engine(self) -> str:
        # Check if user has forced a specific engine in settings
        preferred = None
        try:
            from storage.repository import DeviceRepository
            repo = DeviceRepository()
            preferred = str(repo.get_setting("tts_engine", "auto") or "auto").lower()
        except Exception:
            pass

        has_cartesia = self._check_cartesia()
        has_edge_tts = self._check_edge_tts()
        has_speechify = bool(os.environ.get("SPEECHIFY_API_KEY"))
        has_chatterbox = self._check_chatterbox()
        has_openai_key = bool(os.environ.get("OPENAI_API_KEY"))
        has_piper = shutil.which("piper") and os.path.exists(
            os.getenv("PIPER_MODEL", "/home/pi/bitos/models/tts/en_US-lessac-medium.onnx")
        )
        has_espeak = shutil.which("espeak") or shutil.which("espeak-ng")
        logger.info(
            "tts_detect: preferred=%s cartesia=%s edge_tts=%s speechify=%s chatterbox=%s piper=%s openai=%s espeak=%s",
            preferred, has_cartesia, has_edge_tts, has_speechify, has_chatterbox,
            bool(has_piper), has_openai_key, bool(has_espeak),
        )

        # If user picked a specific engine and it's available, use it
        if preferred and preferred != "auto":
            engine_checks = {
                "cartesia": has_cartesia,
                "edge_tts": has_edge_tts,
                "speechify": has_speechify,
                "chatterbox": has_chatterbox,
                "piper": has_piper,
                "openai": has_openai_key,
                "espeak": has_espeak,
            }
            if preferred in engine_checks and engine_checks[preferred]:
                return preferred
            logger.warning("tts_preferred=%s not available, falling back to auto", preferred)

        # Auto: best available (cartesia first when keyed — lowest latency)
        if has_cartesia:
            return "cartesia"
        if has_edge_tts:
            return "edge_tts"
        if has_speechify:
            return "speechify"
        if has_chatterbox:
            return "chatterbox"
        if has_piper:
            return "piper"
        if has_openai_key:
            return "openai"
        if has_espeak:
            return "espeak"
        return "silent"

    def speak(self, text: str) -> bool:
        if not text.strip():
            return False
        if self.engine == "silent":
            logger.warning("tts_engine=silent; skipping synthesis")
            return False

        logger.info("tts_speak: engine=%s text_len=%d text_preview='%s'",
                     self.engine, len(text), text[:60].replace('\n', ' '))

        t0 = time.monotonic()
        out = Path(tempfile.mkstemp(prefix="bitos_tts_", suffix=".wav")[1])
        try:
            if self.engine == "cartesia":
                self._run_cartesia(text, out)
            elif self.engine == "edge_tts":
                self._run_edge_tts(text, out)
            elif self.engine == "speechify":
                self._run_speechify(text, out)
            elif self.engine == "chatterbox":
                self._run_chatterbox(text, out)
            elif self.engine == "piper":
                self._run_piper(text, out)
            elif self.engine == "openai":
                self._run_openai_tts(text, out)
            elif self.engine == "espeak":
                self._run_espeak(text, out)

            synthesis_ms = int((time.monotonic() - t0) * 1000)
            self.last_synthesis_ms = synthesis_ms

            if not out.exists() or out.stat().st_size == 0:
                logger.warning("tts_speak: output file empty or missing after synthesis (%dms)", synthesis_ms)
                return False

            size = out.stat().st_size
            logger.info("tts_speak: synthesized %d bytes in %dms (ttfb=%dms)",
                        size, synthesis_ms, self.last_ttfb_ms)

            # Only resample if using pygame (desktop); aplay reads WAV headers natively
            from .player import _USE_APLAY
            if not _USE_APLAY:
                self._ensure_48k_stereo_wav(out)
                logger.info("tts_speak: resampled to 48k stereo, %d bytes", out.stat().st_size)

            logger.info("tts_speak: playing audio")
            return self.player.play_file(str(out))
        finally:
            if out.exists():
                out.unlink(missing_ok=True)

    def _run_cartesia(self, text: str, output_file: Path) -> None:
        """Synthesize with Cartesia (~40-150ms TTFB, native WAV output)."""
        t0 = time.monotonic()

        from . import cartesia_provider

        voice = self._voice_id or None
        ok = cartesia_provider.synthesize(text, output_file, voice=voice)
        if ok:
            self.last_ttfb_ms = int((time.monotonic() - t0) * 1000)
            logger.info("cartesia_ttfb: %dms", self.last_ttfb_ms)
        else:
            logger.warning("cartesia_fallback: trying next engine")
            self._run_fallback(text, output_file, skip="cartesia")

    def _run_edge_tts(self, text: str, output_file: Path) -> None:
        """Synthesize with Edge TTS (free Microsoft TTS, ~200ms latency)."""
        t0 = time.monotonic()

        from . import edge_tts_provider

        def on_first_chunk(path):
            self.last_ttfb_ms = int((time.monotonic() - t0) * 1000)
            logger.info("edge_tts_ttfb: %dms", self.last_ttfb_ms)

        voice = self._voice_id or None
        rate = self._voice_params.get("rate")
        pitch = self._voice_params.get("pitch")
        ok = edge_tts_provider.synthesize(text, output_file, voice=voice, rate=rate, pitch=pitch)
        if not ok:
            logger.warning("edge_tts_fallback: trying speechify or next engine")
            self._run_fallback(text, output_file, skip="edge_tts")

    def _run_speechify(self, text: str, output_file: Path) -> None:
        from .speechify import synthesize
        voice = self._voice_id or None
        model = self._voice_params.get("model")
        if not synthesize(text, output_file, voice_id=voice, model=model):
            logger.warning("speechify_fallback: trying next engine")
            self._run_fallback(text, output_file, skip="speechify")

    def _run_fallback(self, text: str, output_file: Path, skip: str = "") -> None:
        """Try fallback engines in order, skipping the one that already failed."""
        fallbacks = [
            ("cartesia", lambda: self._check_cartesia(), self._run_cartesia),
            ("edge_tts", lambda: self._check_edge_tts(), self._run_edge_tts),
            ("speechify", lambda: bool(os.environ.get("SPEECHIFY_API_KEY")), self._run_speechify_direct),
            ("piper", lambda: bool(shutil.which("piper")), self._run_piper),
            ("openai", lambda: bool(os.environ.get("OPENAI_API_KEY")), self._run_openai_tts),
            ("espeak", lambda: bool(shutil.which("espeak") or shutil.which("espeak-ng")), self._run_espeak),
        ]
        for name, check, run in fallbacks:
            if name == skip:
                continue
            if check():
                logger.info("tts_fallback: trying %s", name)
                try:
                    run(text, output_file)
                    if output_file.exists() and output_file.stat().st_size > 0:
                        return
                except Exception as exc:
                    logger.warning("tts_fallback_%s_failed: %s", name, exc)
        logger.error("tts_fallback: all engines failed")

    def _run_speechify_direct(self, text: str, output_file: Path) -> None:
        """Call Speechify without triggering its own fallback chain."""
        from .speechify import synthesize
        synthesize(text, output_file)

    def _run_chatterbox(self, text: str, output_file: Path) -> None:
        """Synthesize speech with Chatterbox Turbo (local 350M model)."""
        import torch
        from chatterbox.tts import ChatterboxTTS

        # Lazy-load model once, cache on instance
        if not hasattr(self, "_chatterbox_model"):
            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
            logger.info("chatterbox_load: device=%s", device)
            self._chatterbox_model = ChatterboxTTS.from_pretrained(device=device)

        model = self._chatterbox_model
        wav_tensor = model.generate(text)

        # wav_tensor is a torch tensor [1, samples] at model.sr sample rate
        import torchaudio
        torchaudio.save(str(output_file), wav_tensor, model.sr)

    def _run_piper(self, text: str, output_file: Path) -> None:
        model = os.getenv("PIPER_MODEL", "/home/pi/bitos/models/tts/en_US-lessac-medium.onnx")
        env = os.environ.copy()
        env["ALSA_DEFAULT_PCM"] = PLAYBACK_DEVICE
        subprocess.run(
            ["piper", "--model", model, "--output_file", str(output_file)],
            input=text.encode("utf-8"),
            check=False,
            timeout=30,
            env=env,
        )

    def _run_openai_tts(self, text: str, output_file: Path) -> None:
        import openai

        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        voice = self._voice_id or "alloy"
        speed = float(self._voice_params.get("speed", 1.0))
        model = self._voice_params.get("model", "tts-1")
        with client.audio.speech.with_streaming_response.create(
            model=model, voice=voice, input=text, speed=speed
        ) as resp:
            resp.stream_to_file(str(output_file))

    def _run_espeak(self, text: str, output_file: Path) -> None:
        espeak_cmd = shutil.which("espeak-ng") or shutil.which("espeak")
        if not espeak_cmd:
            return
        voice = self._voice_id or "en-us"
        speed = str(self._voice_params.get("speed", 150))
        pitch = str(self._voice_params.get("pitch", 50))
        env = os.environ.copy()
        env["ALSA_DEFAULT_PCM"] = PLAYBACK_DEVICE
        subprocess.run([espeak_cmd, "-v", voice, "-s", speed, "-p", pitch, "-w", str(output_file), text], check=False, timeout=20, env=env)

    def _ensure_48k_stereo_wav(self, path: Path) -> None:
        try:
            with wave.open(str(path), "rb") as src:
                in_channels = src.getnchannels()
                in_rate = src.getframerate()
                sample_width = src.getsampwidth()
                frames = src.readframes(src.getnframes())
        except Exception as exc:
            logger.warning("tts_resample: cannot read WAV: %s", exc)
            return

        if sample_width != 2:
            return

        if in_rate == SAMPLE_RATE and in_channels == 2:
            return

        audio = np.frombuffer(frames, dtype=np.int16)
        if in_channels == 2:
            stereo = audio.reshape(-1, 2)
        else:
            mono = audio.reshape(-1, 1)
            stereo = np.repeat(mono, 2, axis=1)

        if in_rate != SAMPLE_RATE and len(stereo) > 1:
            old_idx = np.linspace(0.0, 1.0, num=len(stereo), endpoint=True)
            new_len = int(round(len(stereo) * SAMPLE_RATE / in_rate))
            new_idx = np.linspace(0.0, 1.0, num=max(1, new_len), endpoint=True)
            left = np.interp(new_idx, old_idx, stereo[:, 0]).astype(np.int16)
            right = np.interp(new_idx, old_idx, stereo[:, 1]).astype(np.int16)
            stereo = np.column_stack((left, right))

        with wave.open(str(path), "wb") as dst:
            dst.setnchannels(CHANNELS)
            dst.setsampwidth(2)
            dst.setframerate(SAMPLE_RATE)
            dst.writeframes(stereo.astype(np.int16).tobytes())

    def reload_voice_settings(self) -> None:
        """Re-read voice_id and voice_params from repository. Called after settings sync."""
        try:
            from storage.repository import DeviceRepository
            import json
            repo = DeviceRepository()
            self._voice_id = repo.get_setting("voice_id", None)
            params_raw = repo.get_setting("voice_params", "{}")
            self._voice_params = json.loads(params_raw) if isinstance(params_raw, str) else (params_raw or {})
            # Also re-detect engine in case tts_engine changed
            self.engine = self._detect_engine()
        except Exception:
            pass
