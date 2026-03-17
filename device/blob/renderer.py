"""BlobRendererLite — stripped-down metaball renderer for Pi Zero 2W.

Renders 2-3 blobs at 64x64 resolution using numpy vectorised metaball field.
No spikes, no particles, no turbulence, no glow, no waves, no supersampling.

Features kept:
- Binary threshold metaball rendering
- Spring-lerp blob positions (smooth cushioned movement)
- Asymmetric breathing (40% inhale / 60% exhale)
- Simplex noise-driven wandering
- Audio reactivity (amplitude scales blob radius)
- State-driven animation parameters
- Gesture overlay support

Usage:
    renderer = BlobRendererLite()
    surface = renderer.tick(dt_ms=33, audio_amplitude=0.3)
    scaled = pygame.transform.scale(surface, (240, 240))
"""

from __future__ import annotations

import math

import numpy as np

from blob.noise import noise2d
from blob.states import BlobStateLite, StateConfigLite, STATE_CONFIGS_LITE
from blob.gestures import GestureQueueLite, GESTURE_NEUTRAL

# Render resolution — kept small for Pi Zero performance
RENDER_W = 64
RENDER_H = 64


class _Blob:
    """A single metaball with position, radius, and spring velocity."""

    __slots__ = (
        "x", "y", "radius",
        "vx", "vy",
        "target_x", "target_y", "target_radius",
        "noise_offset_x", "noise_offset_y",
        "phase",
    )

    def __init__(self, x: float = 0.5, y: float = 0.5, radius: float = 0.15):
        self.x = x
        self.y = y
        self.radius = radius
        self.vx = 0.0
        self.vy = 0.0
        self.target_x = x
        self.target_y = y
        self.target_radius = radius
        self.noise_offset_x = float(np.random.uniform(0, 100))
        self.noise_offset_y = float(np.random.uniform(0, 100))
        self.phase = float(np.random.uniform(0, math.tau))


def _spring_lerp(
    current: float,
    target: float,
    velocity: float,
    dt: float,
    stiffness: float = 8.0,
    damping: float = 4.0,
) -> tuple[float, float]:
    """Critically damped spring for organic cushioned movement.

    Returns (new_value, new_velocity).
    """
    dx = target - current
    accel = stiffness * dx - damping * velocity
    velocity += accel * dt
    current += velocity * dt
    return current, velocity


class BlobRendererLite:
    """Lightweight metaball renderer for the Pi Zero 2W companion device.

    Renders at 64x64 internally. Call tick() each frame to get a pygame.Surface.
    """

    def __init__(
        self,
        num_blobs: int = 3,
        width: int = RENDER_W,
        height: int = RENDER_H,
    ):
        self.width = width
        self.height = height

        # Pre-compute normalised coordinate grids
        xx = np.linspace(0, 1, width, dtype=np.float32)
        yy = np.linspace(0, 1, height, dtype=np.float32)
        self._X, self._Y = np.meshgrid(xx, yy)
        self._cx = 0.5
        self._cy = 0.5

        # Threshold for binary rendering
        self._threshold = 1.0

        # Create blobs in a tight cluster around center
        self._blobs: list[_Blob] = []
        num_blobs = max(1, min(num_blobs, 5))
        for i in range(num_blobs):
            angle = math.tau * i / num_blobs
            dist = 0.06 if num_blobs > 1 else 0.0
            bx = self._cx + math.cos(angle) * dist
            by = self._cy + math.sin(angle) * dist
            r = 0.16 if i == 0 else 0.11
            self._blobs.append(_Blob(bx, by, r))

        # State
        self._state = BlobStateLite.IDLE
        self._config: StateConfigLite = STATE_CONFIGS_LITE[self._state]

        # Target config for smooth transitions
        self._breathing_speed = self._config.breathing_speed
        self._breathing_amount = self._config.breathing_amount
        self._movement_speed = self._config.movement_speed
        self._noise_amount = self._config.noise_amount
        self._base_scale = self._config.base_scale
        self._color = self._config.color

        # Gesture system
        self.gestures = GestureQueueLite()

        # Time accumulator
        self._time = 0.0

        # Spring stiffness / damping for position
        self._spring_stiffness = 6.0
        self._spring_damping = 3.5

        # Reusable surface buffer (avoid per-frame allocation)
        self._surface = None

    def set_state(self, state: str) -> None:
        """Change animation state by name (e.g. 'idle', 'listening').

        Unknown state names are silently ignored.
        """
        try:
            new_state = BlobStateLite(state)
        except ValueError:
            return
        if new_state == self._state:
            return
        self._state = new_state
        self._config = STATE_CONFIGS_LITE[new_state]

    def tick(self, dt_ms: float, audio_amplitude: float = 0.0):
        """Advance animation and render one frame.

        Args:
            dt_ms: Delta time in milliseconds.
            audio_amplitude: Audio level 0.0–1.0 for reactivity.

        Returns:
            A pygame.Surface of size (width, height) with the rendered blob.
        """
        import pygame

        dt = max(0.001, dt_ms / 1000.0)
        self._time += dt

        # Smooth parameter transitions toward current state config
        self._smooth_params(dt)

        # Get gesture overlay
        gesture_mods = self.gestures.tick(dt_ms)

        # Update blob positions and radii
        self._animate_blobs(dt, audio_amplitude, gesture_mods)

        # Render metaball field
        bitmap = self._render_field(gesture_mods)

        # Convert to pygame surface
        # bitmap is (H, W) uint8 with 0 or 255
        # Cast to uint16 to avoid overflow when multiplying color channels
        r, g, b = self._color
        bm16 = bitmap.astype(np.uint16)
        rgb = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        rgb[..., 0] = ((bm16 * r) // 255).astype(np.uint8)
        rgb[..., 1] = ((bm16 * g) // 255).astype(np.uint8)
        rgb[..., 2] = ((bm16 * b) // 255).astype(np.uint8)

        # pygame.surfarray.make_surface expects (W, H, 3) — transpose
        surface = pygame.surfarray.make_surface(rgb.transpose(1, 0, 2))
        return surface

    def _smooth_params(self, dt: float) -> None:
        """Exponential decay toward target config params."""
        cfg = self._config
        rate = 0.693 / 0.4  # half-life 0.4s
        factor = 1.0 - math.exp(-rate * dt)

        self._breathing_speed += (cfg.breathing_speed - self._breathing_speed) * factor
        self._breathing_amount += (cfg.breathing_amount - self._breathing_amount) * factor
        self._movement_speed += (cfg.movement_speed - self._movement_speed) * factor
        self._noise_amount += (cfg.noise_amount - self._noise_amount) * factor
        self._base_scale += (cfg.base_scale - self._base_scale) * factor
        # Color snaps immediately (no blend on monochrome)
        self._color = cfg.color

    def _animate_blobs(
        self,
        dt: float,
        audio_amplitude: float,
        gesture_mods: dict[str, float],
    ) -> None:
        """Update blob positions and radii for this frame."""
        t = self._time
        cx, cy = self._cx, self._cy

        # Gesture modifiers
        g_offset_x = gesture_mods.get("offset_x", 0.0)
        g_offset_y = gesture_mods.get("offset_y", 0.0)
        g_scale = gesture_mods.get("scale", 1.0)

        for i, blob in enumerate(self._blobs):
            # Asymmetric breathing: 40% inhale, 60% exhale
            breath_phase = (t * self._breathing_speed + blob.phase) % 1.0
            if breath_phase < 0.4:
                # Inhale (fast rise)
                breath_t = breath_phase / 0.4
                breath = math.sin(breath_t * math.pi * 0.5)
            else:
                # Exhale (slow fall)
                breath_t = (breath_phase - 0.4) / 0.6
                breath = math.cos(breath_t * math.pi * 0.5)

            breath_mod = breath * self._breathing_amount

            # Noise-driven wandering
            noise_x = noise2d(
                blob.noise_offset_x + t * self._movement_speed * 0.5,
                t * 0.3,
            )
            noise_y = noise2d(
                blob.noise_offset_y + t * self._movement_speed * 0.5,
                t * 0.3 + 100.0,
            )

            # Set targets: center + noise offset + gesture offset
            blob.target_x = cx + noise_x * self._noise_amount + g_offset_x
            blob.target_y = cy + noise_y * self._noise_amount + g_offset_y

            # Base radius + breathing + audio + gesture scale + state scale
            audio_boost = audio_amplitude * 0.04
            base_r = (0.16 if i == 0 else 0.11)
            blob.target_radius = (
                base_r * self._base_scale * g_scale
                + breath_mod
                + audio_boost
            )

            # Spring-lerp position
            blob.x, blob.vx = _spring_lerp(
                blob.x, blob.target_x, blob.vx, dt,
                self._spring_stiffness, self._spring_damping,
            )
            blob.y, blob.vy = _spring_lerp(
                blob.y, blob.target_y, blob.vy, dt,
                self._spring_stiffness, self._spring_damping,
            )

            # Radius lerp (simple exponential, no spring)
            blob.radius += (blob.target_radius - blob.radius) * min(1.0, dt * 10.0)

    def _render_field(self, gesture_mods: dict[str, float]) -> np.ndarray:
        """Render the metaball field to a (H, W) uint8 bitmap (0 or 255)."""
        X = self._X
        Y = self._Y

        # Apply gesture squish to coordinate space
        squish_x = gesture_mods.get("squish_x", 1.0)
        squish_y = gesture_mods.get("squish_y", 1.0)
        if abs(squish_x - 1.0) > 0.001 or abs(squish_y - 1.0) > 0.001:
            cx, cy = self._cx, self._cy
            X = cx + (X - cx) * squish_x
            Y = cy + (Y - cy) * squish_y

        # Accumulate metaball field
        field = np.zeros((self.height, self.width), dtype=np.float32)
        for blob in self._blobs:
            dx = X - blob.x
            dy = Y - blob.y
            dist_sq = dx * dx + dy * dy + 1e-7
            field += (blob.radius ** 2) / dist_sq

        # Binary threshold
        bitmap = (field >= self._threshold).astype(np.uint8) * 255
        return bitmap

    @property
    def state(self) -> str:
        """Current state name."""
        return self._state.value

    @property
    def blob_count(self) -> int:
        """Number of blobs."""
        return len(self._blobs)
