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


def wrap_markdown_text(text: str, font, max_width: int) -> list[str]:
    """Word-wrap text while preserving markdown markers.

    Measures line width using stripped (visible) text so markdown syntax
    characters don't waste pixel space, but keeps the markers in the
    returned lines so parse_line() can style them during rendering.

    Args:
        text: Raw text that may contain markdown.
        font: Pygame font for measuring pixel widths.
        max_width: Maximum pixel width per line.

    Returns:
        List of wrapped lines with markdown preserved.
    """
    lines: list[str] = []

    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue

        # Detect block-level prefix (bullet / numbered list) for continuation indent
        indent_prefix = ""
        body = paragraph
        stripped_p = paragraph.strip()
        if stripped_p.startswith("- ") or stripped_p.startswith("* "):
            # Will become bullet char in parse_line; measure with bullet
            indent_prefix = "  "  # continuation lines get 2-space indent
        elif re.match(r"^\d+\.\s", stripped_p):
            m = re.match(r"^(\d+\.)\s", stripped_p)
            if m:
                indent_prefix = " " * (len(m.group(1)) + 1)

        words = paragraph.split(" ")
        current_raw = ""  # with markdown markers

        for word in words:
            test_raw = f"{current_raw} {word}".strip() if current_raw else word
            test_visible = strip_markdown(test_raw)
            w = font.size(test_visible)[0]
            if w <= max_width:
                current_raw = test_raw
            else:
                if current_raw:
                    lines.append(current_raw)
                # Check if word itself fits (with indent for continuation)
                word_with_indent = indent_prefix + word if lines else word
                word_visible = strip_markdown(word_with_indent)
                if font.size(word_visible)[0] <= max_width:
                    current_raw = word_with_indent
                else:
                    # Character-level wrap (rare on 240px display)
                    current_raw = indent_prefix if lines else ""
                    for char in word:
                        test_char = current_raw + char
                        if font.size(strip_markdown(test_char))[0] <= max_width:
                            current_raw = test_char
                        else:
                            if current_raw.strip():
                                lines.append(current_raw)
                            current_raw = char

        if current_raw:
            lines.append(current_raw)

    return lines or [""]
