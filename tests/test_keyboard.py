"""Tests for the on-screen keyboard widget."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "device"))

import pygame
pygame.init()

import pytest
from screens.components.keyboard import OnScreenKeyboard, ALPHA_ROWS, NUMERIC_ROWS
from display.tokens import PHYSICAL_W, PHYSICAL_H


@pytest.fixture
def kb():
    return OnScreenKeyboard(prompt="Name:")


@pytest.fixture
def surface():
    return pygame.Surface((PHYSICAL_W, PHYSICAL_H))


# ── Init tests ───────────────────────────────────────────────────

def test_init_defaults(kb):
    assert kb.active is True
    assert kb.text == ""
    assert kb.prompt == "Name:"
    assert kb._row == 0
    assert kb._col == 0


def test_init_with_initial_text():
    kb = OnScreenKeyboard(initial_text="hello")
    assert kb.text == "hello"


def test_focused_key_starts_at_q(kb):
    assert kb.focused_key == "Q"


# ── Navigation tests ────────────────────────────────────────────

def test_short_press_moves_right(kb):
    kb.handle_action("SHORT_PRESS")
    assert kb.focused_key == "W"
    assert kb._row == 0
    assert kb._col == 1


def test_short_press_wraps_to_next_row(kb):
    # Move across entire row 0 (10 keys: Q-P)
    for _ in range(10):
        kb.handle_action("SHORT_PRESS")
    # Should be on row 1, col 0 = 'A'
    assert kb._row == 1
    assert kb._col == 0
    assert kb.focused_key == "A"


def test_triple_press_moves_left(kb):
    # Move right first
    kb.handle_action("SHORT_PRESS")
    kb.handle_action("SHORT_PRESS")  # at 'E'
    kb.handle_action("TRIPLE_PRESS")  # back to 'W'
    assert kb.focused_key == "W"


def test_triple_press_wraps_to_previous_row(kb):
    # At Q (row 0, col 0), move left wraps to end of last row
    kb.handle_action("TRIPLE_PRESS")
    assert kb._row == 3  # last row
    assert kb.focused_key == "ENTER"


def test_long_press_moves_down(kb):
    kb.handle_action("LONG_PRESS")
    assert kb._row == 1
    assert kb._col == 0
    assert kb.focused_key == "A"


def test_long_press_clamps_col(kb):
    # Row 0 has 10 keys, move to col 9 (P)
    for _ in range(9):
        kb.handle_action("SHORT_PRESS")
    assert kb.focused_key == "P"
    # Move down to row 1 which has 9 keys — col should clamp to 8
    kb.handle_action("LONG_PRESS")
    assert kb._row == 1
    assert kb._col == 8  # clamped to last key in row 1
    assert kb.focused_key == "L"


def test_long_press_wraps_from_last_row(kb):
    # Go to row 3
    kb.handle_action("LONG_PRESS")
    kb.handle_action("LONG_PRESS")
    kb.handle_action("LONG_PRESS")
    assert kb._row == 3
    kb.handle_action("LONG_PRESS")
    assert kb._row == 0  # wraps back to top


# ── Typing tests ─────────────────────────────────────────────────

def test_double_press_types_character(kb):
    # Focus is on Q
    kb.handle_action("DOUBLE_PRESS")
    assert kb.text == "q"


def test_typing_multiple_chars(kb):
    # Type "hi" — H is row1 col5, I is row0 col7
    # Go to row 1
    kb.handle_action("LONG_PRESS")
    # Move to H (col 5)
    for _ in range(5):
        kb.handle_action("SHORT_PRESS")
    assert kb.focused_key == "H"
    kb.handle_action("DOUBLE_PRESS")
    # Now go to I: row 0 col 7
    # Currently on row 1 col 5. Move up via long_press wrapping
    kb._row = 0
    kb._col = 7
    assert kb.focused_key == "I"
    kb.handle_action("DOUBLE_PRESS")
    assert kb.text == "hi"


# ── Backspace test ───────────────────────────────────────────────

def test_backspace_deletes_last_char():
    kb = OnScreenKeyboard(initial_text="abc")
    # Navigate to DEL: row 2, last key
    kb._row = 2
    kb._col = len(ALPHA_ROWS[2]) - 1
    assert kb.focused_key == "DEL"
    kb.handle_action("DOUBLE_PRESS")
    assert kb.text == "ab"


def test_backspace_on_empty():
    kb = OnScreenKeyboard()
    kb._row = 2
    kb._col = len(ALPHA_ROWS[2]) - 1
    kb.handle_action("DOUBLE_PRESS")
    assert kb.text == ""  # no crash


# ── Space test ───────────────────────────────────────────────────

def test_space_key(kb):
    kb._row = 3
    kb._col = 1  # SPACE
    assert kb.focused_key == "SPACE"
    kb.handle_action("DOUBLE_PRESS")
    assert kb.text == " "


# ── Enter / done callback ───────────────────────────────────────

def test_enter_calls_on_done():
    result = {}

    def done_cb(text):
        result["text"] = text

    kb = OnScreenKeyboard(initial_text="test", on_done=done_cb)
    kb._row = 3
    kb._col = 2  # ENTER
    assert kb.focused_key == "ENTER"
    kb.handle_action("DOUBLE_PRESS")
    assert result["text"] == "test"
    assert kb.active is False


def test_tick_returns_false_after_enter():
    kb = OnScreenKeyboard(initial_text="x")
    kb._row = 3
    kb._col = 2
    kb.handle_action("DOUBLE_PRESS")
    assert kb.tick(16) is False


# ── Shift tests ─────────────────────────────────────────────────

def test_shift_toggle(kb):
    assert kb._shifted is False
    kb._row = 2
    kb._col = 0  # SHF
    kb.handle_action("DOUBLE_PRESS")
    assert kb._shifted is True


def test_shift_auto_unshifts(kb):
    # Activate shift
    kb._row = 2
    kb._col = 0
    kb.handle_action("DOUBLE_PRESS")
    assert kb._shifted is True
    # Type a char
    kb._row = 0
    kb._col = 0  # Q
    kb.handle_action("DOUBLE_PRESS")
    assert kb.text == "Q"
    assert kb._shifted is False  # auto-unshifted


# ── Mode toggle tests ───────────────────────────────────────────

def test_mode_toggle_to_numeric(kb):
    kb._row = 3
    kb._col = 0  # "123"
    kb.handle_action("DOUBLE_PRESS")
    assert kb._numeric is True
    assert kb.rows is NUMERIC_ROWS
    assert kb._row == 0
    assert kb._col == 0


def test_mode_toggle_back_to_alpha(kb):
    kb._numeric = True
    kb._row = 3
    kb._col = 0  # "ABC"
    assert kb.focused_key == "ABC"
    kb.handle_action("DOUBLE_PRESS")
    assert kb._numeric is False


# ── Render tests ─────────────────────────────────────────────────

def test_render_no_crash(kb, surface):
    """Render should complete without error."""
    kb.render(surface)


def test_render_inactive_is_noop(surface):
    kb = OnScreenKeyboard()
    kb._active = False
    kb.render(surface)  # Should not crash


def test_render_with_text(surface):
    kb = OnScreenKeyboard(prompt="Msg:", initial_text="hello world")
    kb.render(surface)


# ── Action consumption ───────────────────────────────────────────

def test_consumes_hold_events(kb):
    assert kb.handle_action("HOLD_START") is True
    assert kb.handle_action("HOLD_END") is True


def test_inactive_does_not_consume():
    kb = OnScreenKeyboard()
    kb._active = False
    assert kb.handle_action("SHORT_PRESS") is False
