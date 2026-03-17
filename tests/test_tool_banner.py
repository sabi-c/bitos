"""Tests for in-chat tool result banners — accent colors and rendering."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from device.ui.components.tool_banner import (
    DEFAULT_COLOR,
    TOOL_COLORS,
    ToolBanner,
)


@pytest.fixture(scope="module", autouse=True)
def _init_pygame():
    pygame.init()
    pygame.font.init()
    yield
    pygame.quit()


def test_task_banner_has_purple_accent():
    """Task-related tools should use purple accent."""
    for tool_name in ("create_task", "update_task", "complete_task"):
        banner = ToolBanner(tool=tool_name, summary="Buy milk")
        assert banner.accent_color == (160, 100, 220), f"{tool_name} should be purple"


def test_reminder_banner_has_red_accent():
    """schedule_reminder should use red accent."""
    banner = ToolBanner(tool="schedule_reminder", summary="Stand up in 30m")
    assert banner.accent_color == (220, 80, 80)


def test_calendar_banner_has_green_accent():
    """Calendar event tools should use green accent."""
    for tool_name in ("create_event", "update_event"):
        banner = ToolBanner(tool=tool_name, summary="Meeting at 3pm")
        assert banner.accent_color == (80, 180, 120), f"{tool_name} should be green"


def test_render_smoke():
    """Render a banner with detail line and ensure it returns positive height."""
    surface = pygame.Surface((240, 280))
    banner = ToolBanner(tool="create_task", summary="Buy milk", detail="Added to today")
    height = banner.render(surface, y=10)
    assert height > 0
    # Should be taller than a single-line banner since we have detail
    single = ToolBanner(tool="create_task", summary="Buy milk")
    single_h = single.render(surface, y=100)
    assert height > single_h


def test_render_without_detail():
    """Render a banner without detail — should still return positive height."""
    surface = pygame.Surface((240, 280))
    banner = ToolBanner(tool="homekit", summary="Lights on")
    height = banner.render(surface, y=0)
    assert height > 0
    # Unknown tool falls back to default color
    unknown = ToolBanner(tool="unknown_tool", summary="Something")
    assert unknown.accent_color == DEFAULT_COLOR
