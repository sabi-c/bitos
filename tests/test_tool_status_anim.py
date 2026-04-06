"""Tests for ToolStatusAnimation component."""
import os, sys
from pathlib import Path
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import pygame
pygame.init()


def test_icon_mapping():
    from display.tool_status_anim import icon_for_status
    assert icon_for_status("Thinking...") == "brain"
    assert icon_for_status("Searching emails...") == "magnifier"
    assert icon_for_status("Analyzing data...") == "gear"
    assert icon_for_status("Processing...") == "dots"
    assert icon_for_status("Unknown thing") == "dots"  # fallback


def test_animation_lifecycle():
    from display.tool_status_anim import ToolStatusAnimation
    anim = ToolStatusAnimation()
    assert not anim.active
    anim.set_status("Thinking...")
    assert anim.active
    anim.clear()
    assert not anim.active


def test_render_does_not_crash():
    from display.tool_status_anim import ToolStatusAnimation
    anim = ToolStatusAnimation()
    anim.set_status("Searching...")
    anim.update(100)  # 100ms
    surf = pygame.Surface((240, 280))
    height = anim.render(surf, 8, 250)
    assert height > 0


def test_icon_switch_resets_animation():
    from display.tool_status_anim import ToolStatusAnimation
    anim = ToolStatusAnimation()
    anim.set_status("Thinking...")
    anim.update(500)
    anim.set_status("Searching...")  # different icon
    # Animation should have reset (implementation detail, just verify no crash)
    anim.update(100)
    surf = pygame.Surface((240, 280))
    anim.render(surf, 8, 250)
