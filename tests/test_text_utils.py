"""Tests for display.text_utils.wrap_text."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "device"))

from display.text_utils import wrap_text


class FakeFont:
    """Mimics pygame font .size() using character count * char_width."""

    def __init__(self, char_width: int = 8):
        self._cw = char_width

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * self._cw, 12)


def _make_font(char_width: int = 8) -> FakeFont:
    return FakeFont(char_width)


class TestWrapText:
    def test_empty_string_returns_single_empty(self):
        assert wrap_text("", 100, _make_font()) == [""]

    def test_short_string_single_line(self):
        font = _make_font(8)
        # "hello" = 5 chars * 8px = 40px, fits in 100px
        result = wrap_text("hello", 100, font)
        assert result == ["hello"]

    def test_wraps_at_max_width(self):
        font = _make_font(10)
        # max_width=50 fits 5 chars per line (5*10=50)
        result = wrap_text("abcdefghij", 50, font)
        assert result == ["abcde", "fghij"]

    def test_wraps_multiple_lines(self):
        font = _make_font(10)
        # 12 chars, 5 per line -> 3 lines
        result = wrap_text("abcdefghijkl", 50, font)
        assert result == ["abcde", "fghij", "kl"]

    def test_single_char_per_line(self):
        font = _make_font(10)
        result = wrap_text("abc", 10, font)
        assert result == ["a", "b", "c"]

    def test_returns_list_of_str(self):
        result = wrap_text("test", 200, _make_font())
        assert isinstance(result, list)
        assert all(isinstance(line, str) for line in result)
