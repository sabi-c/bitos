"""Tests for animated toast rendering — progress, slide, category colors."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from overlays.notification import (
    CATEGORY_COLORS,
    TOAST_ENTRANCE_MS,
    TOAST_H,
    NotificationToast,
)


@pytest.fixture(scope="module", autouse=True)
def _init_pygame():
    pygame.init()
    pygame.font.init()
    yield
    pygame.quit()


def _make_toast(**kwargs) -> NotificationToast:
    defaults = dict(
        app="SMS",
        icon="S",
        message="Hey there",
        time_str="14:05",
        category="sms",
    )
    defaults.update(kwargs)
    return NotificationToast(**defaults)


# ── Progress property ─────────────────────────────────────────────────


def test_progress_decreases_with_time():
    toast = _make_toast(duration_ms=1000)
    assert toast.progress == 1.0
    toast.tick(500)
    assert 0.4 < toast.progress < 0.6
    toast.tick(500)
    assert toast.progress == 0.0


# ── Category color ────────────────────────────────────────────────────


def test_has_category_color():
    toast = _make_toast(category="sms")
    assert toast.category_color == CATEGORY_COLORS["sms"]
    # Unknown category falls back to system
    toast2 = _make_toast(category="unknown_thing")
    assert toast2.category_color == CATEGORY_COLORS["system"]


# ── Slide animation ──────────────────────────────────────────────────


def test_slide_entrance_starts_offscreen_then_settles():
    toast = _make_toast(duration_ms=3000)
    # At t=0, should be off-screen (negative y)
    assert toast.slide_y_offset < 0
    # After entrance period, should settle to 0
    toast.elapsed_ms = TOAST_ENTRANCE_MS + 50
    assert toast.slide_y_offset == 0.0


# ── Render smoke test ─────────────────────────────────────────────────


def test_render_smoke_test():
    """Toast renders without crashing at various elapsed times."""

    class FakeTokens:
        WHITE = (255, 255, 255)
        BLACK = (0, 0, 0)
        DIM3 = (80, 80, 80)
        PHYSICAL_W = 240
        PHYSICAL_H = 280
        FONT_PATH = "nonexistent.ttf"
        FONT_SIZES = {"small": 10, "body": 12, "hint": 8}

    surface = pygame.Surface((240, 280))
    tokens = FakeTokens()
    for elapsed in (0, 75, 1500, 2900, 3000):
        toast = _make_toast(duration_ms=3000, category="mail")
        toast.elapsed_ms = elapsed
        toast.render(surface, tokens)  # must not raise
