"""Speechify TTS client — converts text to speech via Speechify API.

Uses the /v1/audio/speech endpoint with base64-encoded audio response.
Falls back gracefully if API key is missing or request fails.
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://api.speechify.ai/v1/audio/speech"
STREAM_URL = "https://api.speechify.ai/v1/audio/stream"
DEFAULT_VOICE = os.getenv("SPEECHIFY_VOICE_ID", "sophia")
DEFAULT_MODEL = os.getenv("SPEECHIFY_MODEL", "simba-english")


def get_api_key() -> str | None:
    return os.environ.get("SPEECHIFY_API_KEY")


def synthesize(text: str, output_path: Path, voice_id: str | None = None) -> bool:
    """Synthesize text to a WAV file via Speechify API.

    Returns True on success, False on any failure.
    """
    api_key = get_api_key()
    if not api_key:
        return False

    voice = voice_id or DEFAULT_VOICE
    try:
        resp = httpx.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "input": text,
                "voice_id": voice,
                "model": DEFAULT_MODEL,
                "audio_format": "wav",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        audio_b64 = data.get("audio_data")
        if not audio_b64:
            logger.warning("speechify: no audio_data in response")
            return False

        audio_bytes = base64.b64decode(audio_b64)
        output_path.write_bytes(audio_bytes)

        chars = data.get("billable_characters_count", len(text))
        logger.info("speechify_ok voice=%s chars=%d bytes=%d", voice, chars, len(audio_bytes))
        return True

    except httpx.TimeoutException:
        logger.warning("speechify_timeout voice=%s text_len=%d", voice, len(text))
        return False
    except httpx.HTTPStatusError as exc:
        logger.warning("speechify_http_error status=%d voice=%s", exc.response.status_code, voice)
        return False
    except Exception as exc:
        logger.warning("speechify_error: %s", exc)
        return False
