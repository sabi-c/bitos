"""Simplified blob state configurations for Pi Zero 2W.

Each state defines animation parameters that shape the blob's personality
and responsiveness. Stripped to five core states — no presets, no manager.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BlobStateLite(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    SLEEPING = "sleeping"


@dataclass(frozen=True)
class StateConfigLite:
    """Animation parameters for a single blob state."""
    breathing_speed: float    # cycles per second
    breathing_amount: float   # radius scale factor (0.0–0.15)
    movement_speed: float     # noise-driven wandering speed multiplier
    noise_amount: float       # how far blobs wander (0.0–0.06)
    base_scale: float         # overall size multiplier (1.0 = default)
    color: tuple[int, int, int]  # RGB color for the blob fill


STATE_CONFIGS_LITE: dict[BlobStateLite, StateConfigLite] = {
    BlobStateLite.IDLE: StateConfigLite(
        breathing_speed=0.8,
        breathing_amount=0.04,
        movement_speed=0.3,
        noise_amount=0.02,
        base_scale=1.0,
        color=(255, 255, 255),
    ),
    BlobStateLite.LISTENING: StateConfigLite(
        breathing_speed=1.2,
        breathing_amount=0.06,
        movement_speed=0.5,
        noise_amount=0.03,
        base_scale=1.05,
        color=(255, 255, 255),
    ),
    BlobStateLite.THINKING: StateConfigLite(
        breathing_speed=0.6,
        breathing_amount=0.03,
        movement_speed=0.8,
        noise_amount=0.04,
        base_scale=0.95,
        color=(255, 255, 255),
    ),
    BlobStateLite.SPEAKING: StateConfigLite(
        breathing_speed=1.5,
        breathing_amount=0.08,
        movement_speed=0.4,
        noise_amount=0.025,
        base_scale=1.08,
        color=(255, 255, 255),
    ),
    BlobStateLite.SLEEPING: StateConfigLite(
        breathing_speed=0.35,
        breathing_amount=0.025,
        movement_speed=0.05,
        noise_amount=0.005,
        base_scale=0.9,
        color=(180, 180, 180),
    ),
}
