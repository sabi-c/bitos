"""Tests for status bar badge animation enhancements."""
import sys
from unittest.mock import MagicMock

import pytest

# Stub pygame before importing status_bar
_pg = MagicMock()
_pg.Surface = MagicMock
_pg.draw = MagicMock()
sys.modules.setdefault("pygame", _pg)

from device.ui.components.status_bar import StatusBar


def test_badge_pulse_time_exists_after_init():
    bar = StatusBar()
    assert hasattr(bar, "_badge_pulse_time")
    assert bar._badge_pulse_time == 0.0


def test_badge_resets_on_zero():
    bar = StatusBar()
    bar.set_unread_count(5, category="sms")
    assert bar.unread_count == 5
    bar.set_unread_count(0)
    assert bar.unread_count == 0


def test_render_with_badge_smoke(monkeypatch):
    """Render with a badge set should not raise."""
    bar = StatusBar()
    bar.set_unread_count(3, category="mail")
    surface = MagicMock()
    surface.blit = MagicMock()
    # get_font returns a mock font whose render returns a mock surface
    mock_font = MagicMock()
    rendered = MagicMock()
    rendered.get_width.return_value = 30
    rendered.get_height.return_value = 10
    mock_font.render.return_value = rendered
    monkeypatch.setattr("device.ui.components.status_bar.get_font", lambda _sz: mock_font)
    bar.render(surface, y=0, width=240)
    # Badge pulse should have advanced
    assert bar._badge_pulse_time > 0.0


def test_category_color_stored():
    bar = StatusBar()
    bar.set_unread_count(1, category="reminder")
    assert bar._badge_color == (220, 80, 80)

    bar.set_unread_count(2, category="task")
    assert bar._badge_color == (160, 100, 220)

    # Unknown category → white fallback
    bar.set_unread_count(1, category="unknown")
    assert bar._badge_color == (255, 255, 255)
