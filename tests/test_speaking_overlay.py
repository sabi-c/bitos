"""Tests for the speaking overlay widget."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import pytest


def test_speaking_overlay_creation():
    from overlays.speaking_overlay import SpeakingOverlay
    overlay = SpeakingOverlay()
    assert overlay.active is False


def test_speaking_overlay_show_hide():
    from overlays.speaking_overlay import SpeakingOverlay
    overlay = SpeakingOverlay()
    overlay.show()
    assert overlay.active is True
    overlay.dismiss()
    assert overlay.active is False


def test_speaking_overlay_tick_animates_dots():
    from overlays.speaking_overlay import SpeakingOverlay
    overlay = SpeakingOverlay()
    overlay.show()
    dots1 = overlay._dots
    overlay.tick(500)
    dots2 = overlay._dots
    assert 0 <= dots1 <= 3
    assert 0 <= dots2 <= 3


def test_speaking_overlay_gesture_short_press_dismisses():
    from overlays.speaking_overlay import SpeakingOverlay
    overlay = SpeakingOverlay()
    overlay.show()
    result = overlay.handle_action("SHORT_PRESS")
    assert result == "skip"  # SHORT_PRESS skips TTS playback


def test_speaking_overlay_gesture_hold_start_replies():
    from overlays.speaking_overlay import SpeakingOverlay
    overlay = SpeakingOverlay()
    overlay.show()
    result = overlay.handle_action("HOLD_START")
    assert result == "reply"


def test_speaking_overlay_inactive_ignores_actions():
    from overlays.speaking_overlay import SpeakingOverlay
    overlay = SpeakingOverlay()
    result = overlay.handle_action("SHORT_PRESS")
    assert result is None
