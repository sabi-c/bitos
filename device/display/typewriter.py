"""TypewriterRenderer — progressive word-by-word text reveal.

Reveals response text at a configurable speed with punctuation-aware pauses.
Call update(dt) each frame, then get_visible_text() for the current state.
"""

from __future__ import annotations

SPEED_PRESETS: dict[str, float] = {
    "slow": 2.0,
    "normal": 3.0,
    "fast": 6.0,
    "instant": float("inf"),
}

PAUSE_PERIOD = 0.4
PAUSE_COMMA = 0.15
PAUSE_PARAGRAPH = 0.6


class TypewriterRenderer:
    """Progressive word-by-word text reveal with punctuation pauses."""

    def __init__(self, text: str, speed: str = "normal"):
        self._words: list[str] = []
        self._pauses: list[float] = []
        self._words_per_sec = SPEED_PRESETS.get(speed, SPEED_PRESETS["normal"])
        self._revealed_count = 0
        self._elapsed = 0.0
        self._next_reveal_at = 0.0
        self._finished = False
        self._parse(text)

    def _parse(self, text: str) -> None:
        if not text:
            self._finished = True
            return

        raw_words = text.split(" ")
        self._words = []
        self._pauses = []

        for w in raw_words:
            if not w:
                continue
            self._words.append(w)
            pause = 0.0
            stripped = w.rstrip()
            if "\n\n" in w:
                pause = PAUSE_PARAGRAPH
            elif stripped.endswith((".", "?", "!")):
                pause = PAUSE_PERIOD
            elif stripped.endswith((",", ":", ";")):
                pause = PAUSE_COMMA
            self._pauses.append(pause)

    def update(self, dt: float) -> None:
        if self._finished or not self._words:
            return

        # Instant speed: reveal everything on first update
        if self._words_per_sec == float("inf"):
            self._revealed_count = len(self._words)
            self._finished = True
            return

        self._elapsed += dt

        if self._elapsed <= 0:
            return

        # First word reveals on any positive elapsed time
        if self._revealed_count == 0:
            self._revealed_count = 1
            # Schedule next word from current time
            if len(self._words) > 1:
                word_interval = 1.0 / self._words_per_sec
                self._next_reveal_at = self._elapsed + self._pauses[0] + word_interval

        # Subsequent words based on scheduled reveal times
        while self._revealed_count < len(self._words) and self._elapsed >= self._next_reveal_at:
            self._revealed_count += 1
            if self._revealed_count < len(self._words):
                word_interval = 1.0 / self._words_per_sec
                extra_pause = self._pauses[self._revealed_count - 1]
                self._next_reveal_at += word_interval + extra_pause

        if self._revealed_count >= len(self._words):
            self._finished = True

    def get_visible_text(self) -> str:
        if not self._words:
            return ""
        return " ".join(self._words[:self._revealed_count])

    @property
    def finished(self) -> bool:
        return self._finished

    def reset(self, text: str, speed: str | None = None) -> None:
        if speed:
            self._words_per_sec = SPEED_PRESETS.get(speed, SPEED_PRESETS["normal"])
        self._revealed_count = 0
        self._elapsed = 0.0
        self._next_reveal_at = 0.0
        self._finished = False
        self._words = []
        self._pauses = []
        self._parse(text)
