"""TypewriterRenderer — character-by-character text reveal.

Reveals text one character at a time with natural typing cadence:
- Common letters faster, rare letters slower
- Micro-jitter for organic feel
- Punctuation pauses at sentence/clause boundaries
- Speed presets for user preference

Call update(dt) each frame, then get_visible_text() for the current state.
"""

from __future__ import annotations

import random

# Speed presets: base milliseconds per character (lower = faster)
SPEED_PRESETS: dict[str, float] = {
    "slow": 80.0,
    "normal": 30.0,
    "fast": 15.0,
    "instant": 0.0,
}

# Post-character pauses in ms
_PAUSE_MS = {
    ".": 280,
    "!": 300,
    "?": 300,
    ",": 120,
    ":": 150,
    ";": 140,
    "\n": 200,
}

_COMMON = frozenset("etaoinsrhld")
_RARE = frozenset("zxqjZXQJ")


def _char_delay_ms(char: str, base_ms: float) -> float:
    """Delay in ms after revealing this character."""
    if char == " ":
        d = base_ms * 0.6
    elif char in _COMMON:
        d = base_ms * 0.8
    elif char in _RARE:
        d = base_ms * 1.3
    else:
        d = base_ms

    # +-15% jitter for organic feel
    d *= random.uniform(0.85, 1.15)

    # Add punctuation pause
    d += _PAUSE_MS.get(char, 0)
    return d


class TypewriterRenderer:
    """Character-by-character text reveal with natural typing cadence."""

    def __init__(self, text: str, speed: str = "normal"):
        self._text = text or ""
        self._base_ms = SPEED_PRESETS.get(speed, SPEED_PRESETS["normal"])
        self._cursor = 0
        self._elapsed = 0.0
        self._next_reveal_at = 0.0
        self._finished = not self._text or self._base_ms == 0.0

        if self._finished and self._text:
            self._cursor = len(self._text)

    def update(self, dt: float) -> None:
        if self._finished:
            return

        self._elapsed += dt

        while self._cursor < len(self._text) and self._elapsed >= self._next_reveal_at:
            char = self._text[self._cursor]
            self._cursor += 1
            delay_ms = _char_delay_ms(char, self._base_ms)
            self._next_reveal_at += delay_ms / 1000.0

        if self._cursor >= len(self._text):
            self._finished = True

    def get_visible_text(self) -> str:
        return self._text[:self._cursor]

    @property
    def finished(self) -> bool:
        return self._finished

    def reset(self, text: str, speed: str | None = None) -> None:
        if speed:
            self._base_ms = SPEED_PRESETS.get(speed, SPEED_PRESETS["normal"])
        self._text = text or ""
        self._cursor = 0
        self._elapsed = 0.0
        self._next_reveal_at = 0.0
        self._finished = not self._text or self._base_ms == 0.0
        if self._finished and self._text:
            self._cursor = len(self._text)
