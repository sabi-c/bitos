"""Tests for status bar badge animation enhancements."""
import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.font.init()

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


def test_render_with_badge_smoke():
    """Render with a badge set should not raise."""
    bar = StatusBar()
    bar.set_unread_count(3, category="mail")
    surface = pygame.Surface((240, 20))
    bar.render(surface, y=0, width=240)
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
