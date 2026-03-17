"""Tests for voice mode setting logic."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import pytest


def test_voice_mode_off_blocks_tts():
    from screens.panels.chat import _should_speak
    assert _should_speak(voice_mode="off", agent_voice_enabled=True, has_api_key=True) is False


def test_voice_mode_on_always_speaks():
    from screens.panels.chat import _should_speak
    assert _should_speak(voice_mode="on", agent_voice_enabled=False, has_api_key=True) is True


def test_voice_mode_auto_respects_agent():
    from screens.panels.chat import _should_speak
    assert _should_speak(voice_mode="auto", agent_voice_enabled=True, has_api_key=True) is True
    assert _should_speak(voice_mode="auto", agent_voice_enabled=False, has_api_key=True) is False


def test_voice_mode_auto_no_key():
    from screens.panels.chat import _should_speak
    assert _should_speak(voice_mode="auto", agent_voice_enabled=True, has_api_key=False) is False


def test_voice_mode_on_no_key():
    from screens.panels.chat import _should_speak
    assert _should_speak(voice_mode="on", agent_voice_enabled=True, has_api_key=False) is False
