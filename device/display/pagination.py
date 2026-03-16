"""Shared pagination utilities for splitting text into device-friendly pages.

Extracted from ChatPanel to be reusable across panels (chat, markdown viewer, etc.).
"""
from __future__ import annotations

import pygame


def split_into_pages(lines: list[str], lines_per_page: int, max_pages: int = 10) -> list[list[str]]:
    """Split wrapped lines into pages, preferring paragraph boundaries.

    Args:
        lines: Pre-wrapped text lines.
        lines_per_page: Maximum lines per page.
        max_pages: Hard cap on page count (default 4). Last page truncates with "...".

    Returns:
        List of pages, each a list of line strings.
    """
    if not lines or lines_per_page <= 0:
        return [lines] if lines else [[]]

    total = len(lines)
    if total <= lines_per_page:
        return [lines]

    pages: list[list[str]] = []
    pos = 0

    while pos < total and len(pages) < max_pages:
        if len(pages) == max_pages - 1:
            # Last allowed page -- take remaining, truncate if needed
            remaining = lines[pos:]
            if len(remaining) > lines_per_page:
                page = remaining[:lines_per_page]
                page[-1] = page[-1].rstrip() + "..."
            else:
                page = remaining
            pages.append(page)
            break

        end = min(pos + lines_per_page, total)

        # Look for paragraph break (empty line) within +/-2 lines of boundary
        best_break = None
        for i in range(max(pos + 1, end - 2), min(end + 3, total)):
            if i < total and lines[i].strip() == "":
                best_break = i + 1  # include the empty line
                break

        if best_break and best_break > pos:
            page = lines[pos:best_break]
        else:
            page = lines[pos:end]

        pages.append(page)
        pos += len(page)

    return pages if pages else [[]]


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width using font metrics.

    Wraps at word boundaries. Falls back to character-level wrapping only
    when a single word exceeds the available width.

    Args:
        text: The text to wrap.
        font: Pygame font used to measure character widths.
        max_width: Maximum pixel width per line.

    Returns:
        List of wrapped line strings.
    """
    lines: list[str] = []

    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue

        words = paragraph.split(" ")
        current = ""

        for word in words:
            # Test if adding this word (with space) fits
            test = f"{current} {word}".strip() if current else word
            if font.size(test)[0] <= max_width:
                current = test
            else:
                # Current line is full — push it
                if current:
                    lines.append(current)

                # Check if the word itself fits on a fresh line
                if font.size(word)[0] <= max_width:
                    current = word
                else:
                    # Word too long — character-level wrap
                    current = ""
                    for char in word:
                        test_char = current + char
                        if font.size(test_char)[0] <= max_width:
                            current = test_char
                        else:
                            if current:
                                lines.append(current)
                            current = char

        if current:
            lines.append(current)

    return lines or [""]
