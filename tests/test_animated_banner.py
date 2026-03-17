"""Tests for animated banner rendering — progress, slide, category colors."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from overlays.notification_banner import (
    BANNER_H,
    CATEGORY_COLORS,
    ENTRANCE_MS,
    EXIT_MS,
    NotificationBanner,
)


@pytest.fixture(scope="module", autouse=True)
def _init_pygame():
    pygame.init()
    pygame.font.init()
    yield
    pygame.quit()


def _make_banner(**kwargs) -> NotificationBanner:
    defaults = dict(
        app="SMS",
        icon="S",
        message="Hey there",
        time_str="14:05",
        category="sms",
    )
    defaults.update(kwargs)
    return NotificationBanner(**defaults)


# ── Progress property ─────────────────────────────────────────────────


def test_has_progress_property():
    banner = _make_banner()
    assert hasattr(banner, "progress")
    assert banner.progress == 1.0


def test_progress_decreases_with_time():
    banner = _make_banner(duration_ms=1000)
    banner.tick(500)
    assert 0.4 < banner.progress < 0.6
    banner.tick(500)
    assert banner.progress == 0.0


# ── Category color ────────────────────────────────────────────────────


def test_has_category_color():
    banner = _make_banner(category="sms")
    assert banner.category_color == CATEGORY_COLORS["sms"]
    # Unknown category falls back to system
    banner2 = _make_banner(category="unknown_thing")
    assert banner2.category_color == CATEGORY_COLORS["system"]


# ── Slide animation ──────────────────────────────────────────────────


def test_slide_offset_starts_offscreen():
    banner = _make_banner()
    # At t=0, should be off-screen (negative y)
    assert banner.slide_y_offset < 0


def test_slide_settles_after_entrance():
    banner = _make_banner(duration_ms=5000)
    banner.elapsed_ms = ENTRANCE_MS + 50  # past entrance, before exit
    assert banner.slide_y_offset == 0.0


def test_exit_animation_starts_near_end():
    banner = _make_banner(duration_ms=5000)
    # Position just inside the exit window
    banner.elapsed_ms = 5000 - EXIT_MS + 10
    offset = banner.slide_y_offset
    # Should be sliding up (negative)
    assert offset < 0


# ── Render smoke test ─────────────────────────────────────────────────


def test_render_smoke_test():
    """Banner renders without crashing at various elapsed times."""
    surface = pygame.Surface((240, 280))
    for elapsed in (0, 100, 7500, 14900, 15000):
        banner = _make_banner(duration_ms=15000, category="mail")
        banner.elapsed_ms = elapsed
        banner.render(surface)  # must not raise
