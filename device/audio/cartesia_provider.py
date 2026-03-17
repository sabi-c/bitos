"""Cartesia TTS provider — ultra-low latency streaming TTS.

~40ms TTFB via WebSocket, ~150ms via HTTP. Native WAV output (no conversion needed).
Same engine used by Open Interpreter 01.

Install: pip install cartesia
Env: CARTESIA_API_KEY, optionally CARTESIA_VOICE_ID, CARTESIA_MODEL_ID
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_VOICE = os.getenv("CARTESIA_VOICE_ID", "79a125e8-cd45-4c13-8a67-188112f4dd22")  # friendly default
DEFAULT_MODEL = os.getenv("CARTESIA_MODEL_ID", "sonic-2024-10-01")
SAMPLE_RATE = 24000


def is_available() -> bool:
    """Return True if cartesia SDK is importable and API key is set."""
    if not os.environ.get("CARTESIA_API_KEY"):
        return False
    try:
        import cartesia  # noqa: F401
        return True
    except ImportError:
        return False


def synthesize(text: str, output_path: Path, voice: str | None = None) -> bool:
    """Synthesize text to WAV file using Cartesia TTS.

    Returns True on success, False on failure.
    """
    if not is_available():
        logger.warning("cartesia: not available (missing SDK or API key)")
        return False

    voice = voice or DEFAULT_VOICE

    try:
        from cartesia import Cartesia

        client = Cartesia(api_key=os.environ["CARTESIA_API_KEY"])

        # Use bytes endpoint — returns WAV chunks directly
        audio_data = client.tts.bytes(
            model_id=DEFAULT_MODEL,
            transcript=text,
            voice_id=voice,
            output_format={
                "container": "wav",
                "encoding": "pcm_s16le",
                "sample_rate": SAMPLE_RATE,
            },
        )

        # Write all chunks to file
        with open(output_path, "wb") as f:
            for chunk in audio_data:
                f.write(chunk)

        if output_path.exists() and output_path.stat().st_size > 44:
            logger.info("cartesia: synthesized %d bytes", output_path.stat().st_size)
            return True

        logger.warning("cartesia: output file empty or too small")
        return False

    except Exception as exc:
        logger.warning("cartesia_error: %s", exc)
        return False
