"""Voice catalog — lists available TTS voices and per-engine parameters."""

from __future__ import annotations

import os
import shutil


def build_catalog(current_engine: str = "auto", current_voice_id: str = "",
                  current_params: dict | None = None) -> dict:
    """Build the full voice catalog with availability checks."""

    engines = {
        "edge_tts": {
            "available": _check_edge_tts(),
            "requires_key": False,
            "voices": [
                {"id": "en-US-AriaNeural", "name": "Aria", "gender": "female", "accent": "US"},
                {"id": "en-US-GuyNeural", "name": "Guy", "gender": "male", "accent": "US"},
                {"id": "en-US-JennyNeural", "name": "Jenny", "gender": "female", "accent": "US"},
                {"id": "en-US-AndrewNeural", "name": "Andrew", "gender": "male", "accent": "US"},
                {"id": "en-GB-SoniaNeural", "name": "Sonia", "gender": "female", "accent": "British"},
                {"id": "en-GB-RyanNeural", "name": "Ryan", "gender": "male", "accent": "British"},
                {"id": "en-AU-NatashaNeural", "name": "Natasha", "gender": "female", "accent": "Australian"},
            ],
            "params": {
                "rate": {"type": "range", "label": "Speed", "min": "-50%", "max": "+50%", "default": "+0%",
                         "description": "Speaking rate adjustment"},
                "pitch": {"type": "range", "label": "Pitch", "min": "-50Hz", "max": "+50Hz", "default": "+0Hz",
                          "description": "Pitch adjustment in Hz"},
            },
        },
        "cartesia": {
            "available": _check_cartesia(),
            "requires_key": True,
            "voices": [
                {"id": "79a125e8-cd45-4c13-8a67-188112f4dd22", "name": "Friendly", "gender": "neutral"},
            ],
            "params": {
                "speed": {"type": "choice", "label": "Speed",
                          "options": ["slowest", "slow", "normal", "fast", "fastest"],
                          "default": "normal", "description": "Speaking speed preset"},
            },
        },
        "speechify": {
            "available": bool(os.environ.get("SPEECHIFY_API_KEY")),
            "requires_key": True,
            "voices": [
                {"id": "sophia", "name": "Sophia", "gender": "female"},
                {"id": "henry", "name": "Henry", "gender": "male"},
                {"id": "george", "name": "George", "gender": "male"},
            ],
            "params": {
                "model": {"type": "choice", "label": "Model",
                          "options": ["simba-english", "simba-turbo"],
                          "default": "simba-english", "description": "Speechify model variant"},
            },
        },
        "openai": {
            "available": bool(os.environ.get("OPENAI_API_KEY")),
            "requires_key": True,
            "voices": [
                {"id": "alloy", "name": "Alloy", "gender": "neutral"},
                {"id": "echo", "name": "Echo", "gender": "male"},
                {"id": "fable", "name": "Fable", "gender": "neutral"},
                {"id": "onyx", "name": "Onyx", "gender": "male"},
                {"id": "nova", "name": "Nova", "gender": "female"},
                {"id": "shimmer", "name": "Shimmer", "gender": "female"},
            ],
            "params": {
                "model": {"type": "choice", "label": "Model",
                          "options": ["tts-1", "tts-1-hd"],
                          "default": "tts-1", "description": "Quality tier (hd = higher quality, slower)"},
                "speed": {"type": "slider", "label": "Speed", "min": 0.25, "max": 4.0,
                          "step": 0.25, "default": 1.0, "description": "Playback speed multiplier"},
            },
        },
        "espeak": {
            "available": bool(shutil.which("espeak") or shutil.which("espeak-ng")),
            "requires_key": False,
            "voices": [
                {"id": "en-us", "name": "English US", "gender": "neutral"},
                {"id": "en-gb", "name": "English UK", "gender": "neutral"},
            ],
            "params": {
                "speed": {"type": "slider", "label": "Speed (wpm)", "min": 80, "max": 350,
                          "step": 10, "default": 150, "description": "Words per minute"},
                "pitch": {"type": "slider", "label": "Pitch", "min": 0, "max": 99,
                          "step": 1, "default": 50, "description": "Voice pitch (0-99)"},
            },
        },
    }

    return {
        "engines": engines,
        "current": {
            "engine": current_engine,
            "voice_id": current_voice_id,
            "params": current_params or {},
        },
    }


def _check_edge_tts() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


def _check_cartesia() -> bool:
    if not os.environ.get("CARTESIA_API_KEY"):
        return False
    try:
        import cartesia  # noqa: F401
        return True
    except ImportError:
        return False
