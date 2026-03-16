"""Lightweight markdown parser for OLED text rendering.

Parses a single line of text into styled segments for pygame rendering.
Supports: **bold**, *italic*, `code`, # headers, - bullets.

On monochrome OLED, styles map to brightness levels rather than font styles:
  bold   → WHITE (full brightness)
  italic → DIM3 (medium)
  code   → DIM2 (dim, monospace feel)
  header → WHITE + larger font
  bullet → indent with bullet char
  normal → default color (usually WHITE for assistant text)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Style constants
STYLE_NORMAL = "normal"
STYLE_BOLD = "bold"
STYLE_ITALIC = "italic"
STYLE_CODE = "code"
STYLE_HEADER = "header"
STYLE_BULLET = "bullet"

# Inline pattern: **bold**, *italic*, `code`
# Order matters — check ** before * to avoid partial matches
_INLINE_RE = re.compile(
    r"(\*\*(.+?)\*\*)"       # **bold**
    r"|(\*(.+?)\*)"          # *italic*
    r"|(`(.+?)`)"            # `code`
)


@dataclass
class Segment:
    """A styled text segment within a line."""
    text: str
    style: str = STYLE_NORMAL


def parse_line(line: str) -> list[Segment]:
    """Parse a single line into styled segments.

    Block-level markers (headers, bullets) apply to the whole line.
    Inline markers (**bold**, *italic*, `code`) split into segments.
    """
    stripped = line.strip()

    if not stripped:
        return [Segment("", STYLE_NORMAL)]

    # Block-level: headers
    if stripped.startswith("# "):
        return [Segment(stripped[2:], STYLE_HEADER)]
    if stripped.startswith("## "):
        return [Segment(stripped[3:], STYLE_HEADER)]
    if stripped.startswith("### "):
        return [Segment(stripped[4:], STYLE_HEADER)]

    # Block-level: bullets
    prefix = ""
    rest = stripped
    if stripped.startswith("- ") or stripped.startswith("* "):
        prefix = "\u2022 "  # bullet char
        rest = stripped[2:]
    elif re.match(r"^\d+\.\s", stripped):
        # Numbered list: keep the number
        match = re.match(r"^(\d+\.)\s(.*)$", stripped)
        if match:
            prefix = match.group(1) + " "
            rest = match.group(2)

    segments = _parse_inline(rest)
    if prefix:
        segments.insert(0, Segment(prefix, STYLE_BULLET))

    return segments


def _parse_inline(text: str) -> list[Segment]:
    """Parse inline markdown into segments."""
    segments: list[Segment] = []
    pos = 0

    for match in _INLINE_RE.finditer(text):
        # Add any text before this match as normal
        if match.start() > pos:
            segments.append(Segment(text[pos:match.start()], STYLE_NORMAL))

        if match.group(2) is not None:  # **bold**
            segments.append(Segment(match.group(2), STYLE_BOLD))
        elif match.group(4) is not None:  # *italic*
            segments.append(Segment(match.group(4), STYLE_ITALIC))
        elif match.group(6) is not None:  # `code`
            segments.append(Segment(match.group(6), STYLE_CODE))

        pos = match.end()

    # Remaining text
    if pos < len(text):
        segments.append(Segment(text[pos:], STYLE_NORMAL))

    return segments if segments else [Segment(text, STYLE_NORMAL)]


def strip_markdown(text: str) -> str:
    """Remove markdown formatting characters from text.

    Useful for word-wrapping calculations where we need clean text width.
    """
    # Remove inline markers
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    # Remove header markers
    text = re.sub(r'^#{1,3}\s+', '', text)
    # Convert bullet markers to bullet char
    text = re.sub(r'^[-*]\s+', '\u2022 ', text)
    return text
