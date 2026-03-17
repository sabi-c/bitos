"""Tests for Focus panel widget strip integration."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "device"))

import pygame
import pytest

from screens.panels.focus import FocusPanel


@pytest.fixture(autouse=True)
def _ensure_pygame():
    pygame.init()
    pygame.font.init()
    yield
    pygame.quit()


def test_has_widget_strip():
    fp = FocusPanel()
    assert hasattr(fp, "_widget_strip")
    assert fp._widget_strip is not None


def test_widget_keys():
    fp = FocusPanel()
    keys = [w.key for w in fp._widget_strip.widgets]
    assert "session" in keys
    assert "elapsed" in keys


def test_render_with_widgets():
    surface = pygame.Surface((240, 280))
    fp = FocusPanel()
    fp.render(surface)


def test_elapsed_updates_on_tick():
    fp = FocusPanel()
    fp._running = True
    fp._remaining_seconds = 1500
    fp._total_seconds = 1500
    fp.update(65.0)  # 65 seconds
    elapsed_widget = [w for w in fp._widget_strip.widgets if w.key == "elapsed"][0]
    assert elapsed_widget.value == "01:05"
