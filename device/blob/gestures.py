"""Single-slot gesture queue for Pi Zero 2W.

Stripped from the full LayeredGestureSystem — one gesture at a time,
simple easing, no crossfade blending. Each gesture modifies position
and scale as an overlay on the current state config.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class GestureLite(Enum):
    BOUNCE = "bounce"
    PULSE = "pulse"
    SQUISH = "squish"
    EXPAND = "expand"
    CONTRACT = "contract"
    WIGGLE = "wiggle"
    NOD = "nod"
    SHAKE = "shake"


# Base durations in seconds
GESTURE_DURATIONS: dict[GestureLite, float] = {
    GestureLite.BOUNCE: 0.8,
    GestureLite.PULSE: 0.6,
    GestureLite.SQUISH: 0.7,
    GestureLite.EXPAND: 0.5,
    GestureLite.CONTRACT: 0.5,
    GestureLite.WIGGLE: 0.9,
    GestureLite.NOD: 0.6,
    GestureLite.SHAKE: 0.7,
}

# Neutral state — no modification
GESTURE_NEUTRAL: dict[str, float] = {
    "offset_x": 0.0,
    "offset_y": 0.0,
    "scale": 1.0,
    "squish_x": 1.0,
    "squish_y": 1.0,
}


@dataclass
class _ActiveGesture:
    """Currently playing gesture."""
    gesture: GestureLite
    duration: float
    time: float = 0.0
    done: bool = False


def _smoothstep(t: float) -> float:
    """Hermite smoothstep for organic easing."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _compute(gesture: _ActiveGesture) -> dict[str, float]:
    """Compute parameter modifications for the current frame."""
    t = gesture.time / max(0.001, gesture.duration)
    t = max(0.0, min(1.0, t))
    g = gesture.gesture

    result = dict(GESTURE_NEUTRAL)

    if g == GestureLite.BOUNCE:
        # Squat anticipation then 3 decaying bounces
        if t < 0.08:
            p = t / 0.08
            squat = math.sin(p * math.pi * 0.5)
            result["squish_y"] = 1.0 - squat * 0.12
            result["squish_x"] = 1.0 + squat * 0.06
        else:
            t_b = (t - 0.08) / 0.92
            bounces = 3
            phase = (t_b * bounces) % 1.0
            decay = 1.0 - t_b * 0.7
            if phase < 0.5:
                p = phase / 0.5
                height = math.sin(p * math.pi) * 0.06 * decay
                result["offset_y"] = -height
                result["squish_y"] = 1.0 + height * 3
                result["squish_x"] = 1.0 - height * 1.5
            else:
                p = (phase - 0.5) / 0.5
                squash = math.sin(p * math.pi * 0.5) * 0.15 * decay
                result["squish_y"] = 1.0 - squash
                result["squish_x"] = 1.0 + squash * 0.6

    elif g == GestureLite.PULSE:
        # Anticipation gather then expand with damped settle
        if t < 0.06:
            p = t / 0.06
            result["scale"] = 1.0 - math.sin(p * math.pi * 0.5) * 0.04
        elif t < 0.3:
            p = (t - 0.06) / 0.24
            pulse = math.sin(p * math.pi)
            result["scale"] = 1.0 + pulse * 0.25
            result["offset_y"] = -pulse * 0.012
        else:
            p = (t - 0.3) / 0.7
            decay = math.exp(-p * 5)
            wobble = math.cos(p * 8) * decay
            result["scale"] = 1.0 + wobble * 0.08

    elif g == GestureLite.SQUISH:
        # Horizontal squish then vertical stretch
        if t < 0.3:
            p = t / 0.3
            squish = math.sin(p * math.pi) * 0.3
            result["squish_x"] = 1.0 + squish
            result["squish_y"] = 1.0 - squish * 0.6
        elif t < 0.6:
            p = (t - 0.3) / 0.3
            stretch = math.sin(p * math.pi) * 0.2
            result["squish_x"] = 1.0 - stretch * 0.5
            result["squish_y"] = 1.0 + stretch

    elif g == GestureLite.EXPAND:
        # Smooth bell-curve scale up then settle
        envelope = math.sin(t * math.pi)
        result["scale"] = 1.0 + envelope * 0.2

    elif g == GestureLite.CONTRACT:
        # Smooth bell-curve scale down then settle
        envelope = math.sin(t * math.pi)
        result["scale"] = 1.0 - envelope * 0.15

    elif g == GestureLite.WIGGLE:
        # Playful side-to-side wobble
        freq = 4
        envelope = math.sin(t * math.pi)
        result["offset_x"] = math.sin(t * freq * math.tau) * 0.03 * envelope
        result["squish_x"] = 1.0 + math.sin(t * freq * math.tau) * 0.08 * envelope

    elif g == GestureLite.NOD:
        # Quick down-up-down motion
        if t < 0.25:
            result["offset_y"] = math.sin(t / 0.25 * math.pi) * 0.04
            result["squish_y"] = 1.0 - math.sin(t / 0.25 * math.pi) * 0.1
        elif t < 0.5:
            p = (t - 0.25) / 0.25
            result["offset_y"] = -math.sin(p * math.pi) * 0.02
            result["squish_y"] = 1.0 + math.sin(p * math.pi) * 0.05
        elif t < 0.75:
            p = (t - 0.5) / 0.25
            result["offset_y"] = math.sin(p * math.pi) * 0.015

    elif g == GestureLite.SHAKE:
        # Rapid decaying left-right shake
        envelope = 1.0 - t
        shake = math.sin(t * 3 * math.tau)
        result["offset_x"] = shake * 0.05 * envelope
        result["squish_x"] = 1.0 + shake * 0.06 * envelope
        result["squish_y"] = 1.0 - abs(shake) * 0.03 * envelope

    return result


class GestureQueueLite:
    """Single-slot gesture queue — one gesture at a time, no layering.

    When a new gesture is triggered, the current one is replaced immediately.
    A brief blend-out returns to neutral after the gesture ends.
    """

    def __init__(self):
        self._current: _ActiveGesture | None = None
        self._blend_time: float = 0.15  # seconds to blend out to neutral
        self._prev_result: dict[str, float] = dict(GESTURE_NEUTRAL)

    def trigger(self, gesture_name: str) -> None:
        """Trigger a gesture by name. Unknown names are silently ignored."""
        try:
            g = GestureLite(gesture_name)
        except ValueError:
            return
        self._current = _ActiveGesture(
            gesture=g,
            duration=GESTURE_DURATIONS[g],
        )

    def tick(self, dt_ms: float) -> dict[str, float]:
        """Advance gesture and return parameter modifications.

        Args:
            dt_ms: Delta time in milliseconds.

        Returns:
            Dict with offset_x, offset_y, scale, squish_x, squish_y.
        """
        dt = dt_ms / 1000.0
        neutral = dict(GESTURE_NEUTRAL)

        if self._current is None:
            self._prev_result = neutral
            return neutral

        self._current.time += dt

        if self._current.time >= self._current.duration:
            # Blend out to neutral
            overshoot = self._current.time - self._current.duration
            if overshoot < self._blend_time and self._prev_result:
                fade = min(1.0, overshoot / self._blend_time)
                fade = _smoothstep(fade)
                result = self._lerp(self._prev_result, neutral, fade)
                self._prev_result = result
                return result
            # Done
            self._current = None
            self._prev_result = neutral
            return neutral

        result = _compute(self._current)
        self._prev_result = result
        return result

    @property
    def active(self) -> bool:
        """True if a gesture is currently playing (including blend-out)."""
        return self._current is not None

    @staticmethod
    def _lerp(a: dict, b: dict, t: float) -> dict[str, float]:
        """Linearly interpolate between two param dicts."""
        result = {}
        for key in ("offset_x", "offset_y"):
            result[key] = a.get(key, 0.0) * (1 - t) + b.get(key, 0.0) * t
        for key in ("scale", "squish_x", "squish_y"):
            result[key] = a.get(key, 1.0) * (1 - t) + b.get(key, 1.0) * t
        return result
