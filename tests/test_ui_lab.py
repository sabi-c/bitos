"""Tests for the UI Lab panel and AnimationOverlay wrapper."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import pygame
import pytest

pygame.init()
pygame.font.init()

from screens.panels.ui_lab import UILabPanel, AnimationOverlay
from screens.components import CheckmarkAnimation, ToastAnimation


def test_ui_lab_has_nav_items():
    panel = UILabPanel()
    assert len(panel._nav.items) >= 7


def test_ui_lab_render():
    surface = pygame.Surface((240, 280))
    panel = UILabPanel()
    panel.render(surface)


def test_ui_lab_navigation():
    panel = UILabPanel()
    panel.handle_action("SHORT_PRESS")
    assert panel._nav.focus_index == 1


def test_ui_lab_navigate_back():
    panel = UILabPanel()
    panel.handle_action("SHORT_PRESS")
    panel.handle_action("SHORT_PRESS")
    panel.handle_action("TRIPLE_PRESS")
    assert panel._nav.focus_index == 1


def test_animation_overlay_wraps_checkmark():
    anim = CheckmarkAnimation(text="TEST")
    overlay = AnimationOverlay(anim)
    assert not overlay.dismissed
    assert overlay.tick(100) is True


def test_animation_overlay_finishes():
    anim = CheckmarkAnimation(text="TEST", duration_ms=100)
    overlay = AnimationOverlay(anim)
    overlay.tick(200)
    assert overlay.dismissed


def test_animation_overlay_doesnt_consume_actions():
    anim = CheckmarkAnimation(text="TEST")
    overlay = AnimationOverlay(anim)
    assert overlay.handle_action("SHORT_PRESS") is False


def test_toast_overlay():
    anim = ToastAnimation(text="OK", style="success", duration_ms=100)
    overlay = AnimationOverlay(anim)
    assert overlay.tick(50) is True
    overlay.tick(100)
    assert overlay.dismissed


def test_animation_overlay_render():
    anim = CheckmarkAnimation(text="RENDER")
    overlay = AnimationOverlay(anim)
    surface = pygame.Surface((240, 280))
    overlay.tick(100)
    overlay.render(surface)


def test_ui_lab_keyboard_action_calls_overlay():
    pushed = []
    panel = UILabPanel(on_show_overlay=lambda o: pushed.append(o))
    # Focus is on KEYBOARD (index 0), activate it
    panel.handle_action("DOUBLE_PRESS")
    assert len(pushed) == 1


def test_ui_lab_widget_demo():
    panel = UILabPanel()
    # Navigate to WIDGETS (index 7)
    for _ in range(7):
        panel.handle_action("SHORT_PRESS")
    panel.handle_action("DOUBLE_PRESS")
    assert panel._showing_widgets is True
    # Render in widget mode
    surface = pygame.Surface((240, 280))
    panel.render(surface)
    # LONG_PRESS exits widget view
    panel.handle_action("LONG_PRESS")
    assert panel._showing_widgets is False
