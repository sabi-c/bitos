"""Shared pagination utilities for splitting text into device-friendly pages.

Extracted from ChatPanel to be reusable across panels (chat, markdown viewer, etc.).
"""
from __future__ import annotations

import pygame


def split_into_pages(lines: list[str], lines_per_page: int, max_pages: int = 4) -> list[list[str]]:
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

    Handles explicit newlines and wraps at character level when a word
    exceeds the available width.

    Args:
        text: The text to wrap.
        font: Pygame font used to measure character widths.
        max_width: Maximum pixel width per line.

    Returns:
        List of wrapped line strings.
    """
    lines = []
    current = ""
    for char in text:
        if char == "\n":
            lines.append(current)
            current = ""
            continue
        test = current + char
        w = font.size(test)[0]
        if w <= max_width:
            current = test
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines or [""]
