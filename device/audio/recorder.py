"""Audio recorder helpers for WM8960 (card 0, device 0)."""

from __future__ import annotations

import logging
import os
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path



logger = logging.getLogger(__name__)

RECORD_DEVICE = os.getenv("ALSA_RECORD_DEVICE", "hw:0,0")
SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", os.getenv("ALSA_SAMPLE_RATE", "48000")))
CHANNELS = int(os.getenv("AUDIO_CHANNELS", "2"))
SAMPLE_WIDTH_BYTES = 2
PCM_FORMAT = "S16_LE"


@dataclass
class RecorderConfig:
    device: str = RECORD_DEVICE
    sample_rate: int = SAMPLE_RATE
    channels: int = CHANNELS
    sample_width: int = SAMPLE_WIDTH_BYTES
    pcm_format: str = PCM_FORMAT


class AudioRecorder:
    """Records stereo 48kHz 16-bit PCM with arecord for WM8960."""

    def __init__(self, config: RecorderConfig | None = None):
        self.config = config or RecorderConfig()

    def record_to_wav(self, output_path: str, seconds: float = 3.0) -> str:
        duration = max(1, int(round(seconds)))
        cmd = [
            "arecord",
            "-D",
            self.config.device,
            "-f",
            self.config.pcm_format,
            "-r",
            str(self.config.sample_rate),
            "-c",
            str(self.config.channels),
            "-d",
            str(duration),
            output_path,
        ]
        logger.info("record_cmd=%s", " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"arecord failed ({proc.returncode}): {proc.stderr.strip()}")
        return output_path

    def record_for_stt(self, output_path: str, seconds: float = 3.0) -> str:
        """Record stereo wav and convert to mono wav for STT."""
        stereo_path = output_path
        self.record_to_wav(stereo_path, seconds=seconds)
        mono_path = str(Path(output_path).with_suffix(".mono.wav"))
        self.stereo_to_mono_wav(stereo_path, mono_path)
        return mono_path

    def stereo_to_mono_wav(self, input_path: str, output_path: str) -> str:
        with wave.open(input_path, "rb") as src:
            channels = src.getnchannels()
            sample_width = src.getsampwidth()
            rate = src.getframerate()
            frames = src.readframes(src.getnframes())

        if sample_width != SAMPLE_WIDTH_BYTES:
            raise RuntimeError(f"unsupported sample width: {sample_width}")

        sample_count = len(frames) // SAMPLE_WIDTH_BYTES
        if sample_count == 0:
            mono_frames = b""
        elif channels == 2:
            data = memoryview(frames).cast("h")
            mono_samples = bytearray()
            for i in range(0, len(data), 2):
                mixed = int((int(data[i]) + int(data[i + 1])) / 2.0)
                mono_samples.extend(int(mixed).to_bytes(2, byteorder="little", signed=True))
            mono_frames = bytes(mono_samples)
        elif channels == 1:
            mono_frames = frames
        else:
            raise RuntimeError(f"unsupported channel count: {channels}")

        with wave.open(output_path, "wb") as dst:
            dst.setnchannels(1)
            dst.setsampwidth(SAMPLE_WIDTH_BYTES)
            dst.setframerate(rate)
            dst.writeframes(mono_frames)
        return output_path
