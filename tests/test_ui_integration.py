"""Integration tests: keyboard + confirm dialogue overlays wire into ScreenManager."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "device"))

import pygame
import pytest

from screens.manager import ScreenManager
from overlays.confirm_dialogue import ConfirmDialogue
from screens.components.keyboard import OnScreenKeyboard


@pytest.fixture(autouse=True)
def _ensure_pygame():
    pygame.init()
    pygame.font.init()
    yield
    pygame.quit()


# Test that overlays integrate with ScreenManager

def test_push_keyboard_overlay():
    sm = ScreenManager()
    kb = OnScreenKeyboard(prompt="REPLY")
    sm.push_overlay(kb)
    assert sm._active_overlay is kb


def test_push_confirm_dialogue():
    sm = ScreenManager()
    d = ConfirmDialogue(title="DELETE?", message="Cannot undo.")
    sm.push_overlay(d)
    assert sm._active_overlay is d


def test_confirm_dialogue_auto_clears():
    sm = ScreenManager()
    d = ConfirmDialogue(title="T", message="M")
    sm.push_overlay(d)
    d.handle_action("LONG_PRESS")  # cancel
    sm.update(0.1)  # tick should clear it
    assert sm._active_overlay is None


def test_keyboard_auto_clears_on_enter():
    sm = ScreenManager()
    kb = OnScreenKeyboard(initial_text="test")
    sm.push_overlay(kb)
    kb._row = 3
    kb._col = 2  # ENTER key
    kb.handle_action("DOUBLE_PRESS")
    sm.update(0.1)
    assert sm._active_overlay is None


def test_confirm_dialogue_action_dispatched_via_manager():
    """ScreenManager.handle_action routes to overlay's handle_action, not handle_input."""
    sm = ScreenManager()
    d = ConfirmDialogue(title="T", message="M")
    sm.push_overlay(d)
    # Toggle selection from cancel(0) to confirm(1)
    sm.handle_action("SHORT_PRESS")
    assert d._selected == 1


def test_keyboard_action_dispatched_via_manager():
    """ScreenManager.handle_action routes to keyboard's handle_action."""
    sm = ScreenManager()
    kb = OnScreenKeyboard(prompt="TEST")
    sm.push_overlay(kb)
    # Move right
    sm.handle_action("SHORT_PRESS")
    assert kb._col == 1 or kb._row != 0  # moved from initial position
