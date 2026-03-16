"""Shared text utilities for display panels."""

from __future__ import annotations


def wrap_text(text: str, max_width: int, font) -> list[str]:
    """Character-level word wrap using a pygame-style font for measurement.

    Args:
        text: The string to wrap.
        max_width: Maximum pixel width per line.
        font: Any object with a ``.size(str) -> (w, h)`` method (e.g. pygame.font.Font).

    Returns:
        A list of wrapped lines.  Returns ``[""]`` for empty input.
    """
    if not text:
        return [""]
    out: list[str] = []
    cur = ""
    for char in text:
        test = cur + char
        if font.size(test)[0] <= max_width:
            cur = test
        else:
            out.append(cur)
            cur = char
    if cur:
        out.append(cur)
    return out
