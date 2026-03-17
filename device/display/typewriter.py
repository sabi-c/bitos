"""TypewriterRenderer — character-by-character text reveal.

Reveals text one character at a time with natural typing cadence:
- Common letters faster, rare letters slower
- Micro-jitter for organic feel
- Punctuation pauses at sentence/clause boundaries
- Speed presets and custom config for fine-tuning

Call update(dt) each frame, then get_visible_text() for the current state.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict


# Post-character pauses in ms (base values, scaled by punctuation_multiplier)
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


@dataclass
class TypewriterConfig:
    """All tunable parameters for typewriter text reveal."""
    base_speed_ms: float = 45.0
    punctuation_multiplier: float = 1.0
    jitter_amount: float = 0.15
    common_speedup: float = 0.8
    rare_slowdown: float = 1.3

    @classmethod
    def from_preset(cls, preset: str) -> TypewriterConfig:
        """Create config from a named preset."""
        presets = {
            "slow": cls(base_speed_ms=80.0),
            "normal": cls(),
            "fast": cls(base_speed_ms=20.0),
            "instant": cls(base_speed_ms=0.0),
        }
        return presets.get(preset, cls())

    @classmethod
    def from_dict(cls, d: dict) -> TypewriterConfig:
        """Create config from a dict, using defaults for missing keys."""
        defaults = cls()
        return cls(
            base_speed_ms=float(d.get("base_speed_ms", defaults.base_speed_ms)),
            punctuation_multiplier=float(d.get("punctuation_multiplier", defaults.punctuation_multiplier)),
            jitter_amount=float(d.get("jitter_amount", defaults.jitter_amount)),
            common_speedup=float(d.get("common_speedup", defaults.common_speedup)),
            rare_slowdown=float(d.get("rare_slowdown", defaults.rare_slowdown)),
        )

    @classmethod
    def from_json(cls, json_str: str) -> TypewriterConfig:
        """Create config from a JSON string."""
        try:
            return cls.from_dict(json.loads(json_str))
        except (json.JSONDecodeError, TypeError):
            return cls()

    def to_dict(self) -> dict:
        return asdict(self)


# Speed presets for backward compatibility
SPEED_PRESETS: dict[str, float] = {
    "slow": 80.0,
    "normal": 45.0,
    "fast": 20.0,
    "instant": 0.0,
}


def _char_delay_ms(char: str, config: TypewriterConfig) -> float:
    """Delay in ms after revealing this character."""
    base = config.base_speed_ms

    if char == " ":
        d = base * 0.6
    elif char in _COMMON:
        d = base * config.common_speedup
    elif char in _RARE:
        d = base * config.rare_slowdown
    else:
        d = base

    # Jitter for organic feel
    if config.jitter_amount > 0:
        jitter = config.jitter_amount
        d *= random.uniform(1.0 - jitter, 1.0 + jitter)

    # Add punctuation pause (scaled by multiplier)
    pause = _PAUSE_MS.get(char, 0)
    if pause:
        d += pause * config.punctuation_multiplier

    return d


class TypewriterRenderer:
    """Character-by-character text reveal with natural typing cadence."""

    def __init__(self, text: str, speed: str = "normal", config: TypewriterConfig | None = None):
        self._text = text or ""
        if config:
            self._config = config
        else:
            self._config = TypewriterConfig.from_preset(speed)

        self._cursor = 0
        self._elapsed = 0.0
        self._next_reveal_at = 0.0
        self._finished = not self._text or self._config.base_speed_ms == 0.0

        if self._finished and self._text:
            self._cursor = len(self._text)

    def update(self, dt: float) -> None:
        if self._finished:
            return

        self._elapsed += dt

        while self._cursor < len(self._text) and self._elapsed >= self._next_reveal_at:
            char = self._text[self._cursor]
            self._cursor += 1
            delay_ms = _char_delay_ms(char, self._config)
            self._next_reveal_at += delay_ms / 1000.0

        if self._cursor >= len(self._text):
            self._finished = True

    def get_visible_text(self) -> str:
        return self._text[:self._cursor]

    @property
    def finished(self) -> bool:
        return self._finished

    def reset(self, text: str, speed: str | None = None, config: TypewriterConfig | None = None) -> None:
        if config:
            self._config = config
        elif speed:
            self._config = TypewriterConfig.from_preset(speed)
        self._text = text or ""
        self._cursor = 0
        self._elapsed = 0.0
        self._next_reveal_at = 0.0
        self._finished = not self._text or self._config.base_speed_ms == 0.0
        if self._finished and self._text:
            self._cursor = len(self._text)
