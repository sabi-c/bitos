"""Tests for ConfirmDialogue overlay."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from overlays.confirm_dialogue import ConfirmDialogue


@pytest.fixture(scope="module", autouse=True)
def _init_pygame():
    pygame.init()
    pygame.font.init()
    yield
    pygame.quit()


def _surface() -> pygame.Surface:
    return pygame.Surface((240, 280))


# ── Lifecycle ────────────────────────────────────────────────────────


def test_starts_not_dismissed():
    d = ConfirmDialogue()
    assert not d.dismissed
    assert d.result is None


def test_tick_keeps_alive():
    d = ConfirmDialogue(timeout_ms=5000)
    assert d.tick(1000)
    assert not d.dismissed


def test_timeout_dismisses():
    d = ConfirmDialogue(timeout_ms=500)
    d.tick(600)
    assert d.dismissed
    assert d.result == "cancel"


# ── Button navigation ────────────────────────────────────────────────


def test_default_selection_is_cancel():
    d = ConfirmDialogue()
    assert d._selected == 0  # cancel


def test_short_press_toggles_selection():
    d = ConfirmDialogue()
    assert d._selected == 0
    d.handle_action("SHORT_PRESS")
    assert d._selected == 1
    d.handle_action("SHORT_PRESS")
    assert d._selected == 0


def test_triple_press_toggles_selection():
    d = ConfirmDialogue()
    d.handle_action("TRIPLE_PRESS")
    assert d._selected == 1


# ── Confirm / Cancel actions ─────────────────────────────────────────


def test_double_press_on_cancel_dismisses_with_cancel():
    results = []
    d = ConfirmDialogue(on_cancel=lambda: results.append("cancelled"))
    # _selected defaults to 0 (cancel)
    d.handle_action("DOUBLE_PRESS")
    assert d.dismissed
    assert d.result == "cancel"
    assert results == ["cancelled"]


def test_double_press_on_confirm_dismisses_with_confirm():
    results = []
    d = ConfirmDialogue(on_confirm=lambda: results.append("confirmed"))
    d.handle_action("SHORT_PRESS")  # select confirm
    d.handle_action("DOUBLE_PRESS")
    assert d.dismissed
    assert d.result == "confirm"
    assert results == ["confirmed"]


def test_long_press_always_cancels():
    results = []
    d = ConfirmDialogue(on_cancel=lambda: results.append("cancelled"))
    d.handle_action("SHORT_PRESS")  # move to confirm
    assert d._selected == 1
    d.handle_action("LONG_PRESS")   # but long press = cancel
    assert d.dismissed
    assert d.result == "cancel"
    assert results == ["cancelled"]


# ── Gesture consumption ──────────────────────────────────────────────


def test_consumes_all_actions_while_active():
    d = ConfirmDialogue()
    assert d.handle_action("HOLD_START") is True
    assert d.handle_action("HOLD_END") is True
    assert not d.dismissed  # did not dismiss


def test_does_not_consume_after_dismissed():
    d = ConfirmDialogue()
    d.handle_action("LONG_PRESS")  # dismiss
    assert d.dismissed
    assert d.handle_action("SHORT_PRESS") is False


# ── Render ───────────────────────────────────────────────────────────


def test_render_no_crash():
    surf = _surface()
    d = ConfirmDialogue(title="DELETE?", message="This cannot be undone.", destructive=True)
    d.render(surf)  # must not raise


def test_render_after_dismissed_is_noop():
    surf = _surface()
    d = ConfirmDialogue()
    d.handle_action("LONG_PRESS")
    assert d.dismissed
    surf.fill((0, 0, 0))
    before = surf.get_at((120, 140))
    d.render(surf)
    after = surf.get_at((120, 140))
    assert before == after


def test_render_without_message():
    surf = _surface()
    d = ConfirmDialogue(title="CONFIRM", message="")
    d.render(surf)  # must not raise


def test_destructive_flag_stored():
    d = ConfirmDialogue(destructive=True)
    assert d.destructive is True
