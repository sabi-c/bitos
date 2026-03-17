"""Lightweight blob renderer for the device display.

Renders a simple animated metaball-style blob on a pygame Surface.
Designed for 240x280 display — no numpy dependency, pure pygame.

States drive visual behavior:
  IDLE      — gentle breathing pulse
  LISTENING — expands + audio-reactive wobble
  THINKING  — slow rotation + shrink-pulse
  SPEAKING  — rhythmic pulse synced to amplitude
"""

from __future__ import annotations

import math
import time
from enum import Enum, auto


class BlobState(Enum):
    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()


class BlobRendererLite:
    """Procedural blob renderer using pygame primitives.

    Draws a cluster of overlapping circles with animated offsets
    to create an organic, ferrofluid-inspired shape.
    """

    def __init__(self, cx: int = 120, cy: int = 90, base_radius: int = 32):
        self.cx = cx
        self.cy = cy
        self.base_radius = base_radius
        self.state = BlobState.IDLE
        self.amplitude: float = 0.0  # 0.0–1.0, fed from mic or TTS
        self._t0 = time.monotonic()
        # Sub-blob offsets (angle, distance_factor, radius_factor)
        self._blobs = [
            (0.0, 0.0, 1.0),        # center
            (0.0, 0.45, 0.55),       # top
            (math.pi * 0.5, 0.45, 0.55),
            (math.pi, 0.45, 0.55),
            (math.pi * 1.5, 0.45, 0.55),
            (math.pi * 0.25, 0.35, 0.4),
            (math.pi * 0.75, 0.35, 0.4),
            (math.pi * 1.25, 0.35, 0.4),
            (math.pi * 1.75, 0.35, 0.4),
        ]

    def set_state(self, state: BlobState) -> None:
        self.state = state

    def set_amplitude(self, amplitude: float) -> None:
        """Set audio amplitude (0.0–1.0) for reactive animation."""
        self.amplitude = max(0.0, min(1.0, amplitude))

    def render(self, surface, color=(255, 255, 255)) -> None:
        """Draw the blob onto a pygame Surface."""
        import pygame

        t = time.monotonic() - self._t0
        state = self.state
        amp = self.amplitude

        # State-dependent animation parameters
        if state == BlobState.IDLE:
            # Gentle breathing
            breath = 1.0 + 0.06 * math.sin(t * 1.8)
            wobble = 0.02
            rotation_speed = 0.3
            scale = breath
        elif state == BlobState.LISTENING:
            # Expanded + audio reactive
            react = 0.15 * amp
            breath = 1.12 + 0.04 * math.sin(t * 2.5) + react
            wobble = 0.08 + 0.12 * amp
            rotation_speed = 0.6 + amp * 0.8
            scale = breath
        elif state == BlobState.THINKING:
            # Slow pulse, contracted
            breath = 0.92 + 0.08 * math.sin(t * 1.2)
            wobble = 0.04
            rotation_speed = 1.5
            scale = breath
        elif state == BlobState.SPEAKING:
            # Rhythmic pulse with amplitude
            react = 0.18 * amp
            breath = 1.0 + 0.05 * math.sin(t * 3.0) + react
            wobble = 0.06 + 0.1 * amp
            rotation_speed = 0.8
            scale = breath
        else:
            scale = 1.0
            wobble = 0.02
            rotation_speed = 0.3

        base_r = self.base_radius * scale

        for i, (angle, dist_f, r_f) in enumerate(self._blobs):
            # Animate offset angle
            a = angle + t * rotation_speed + wobble * math.sin(t * 3.7 + i * 1.3)
            dist = base_r * dist_f
            r = int(base_r * r_f)

            bx = int(self.cx + dist * math.cos(a))
            by = int(self.cy + dist * math.sin(a))

            # Draw filled circle with slight alpha variation
            # Main blob uses solid color; sub-blobs slightly dimmer
            if i == 0:
                c = color
            else:
                # Slightly dimmed for depth
                c = tuple(max(0, min(255, int(v * 0.85))) for v in color)

            pygame.draw.circle(surface, c, (bx, by), max(1, r))

    def render_glow(self, surface, color=(255, 255, 255), glow_alpha: int = 30) -> None:
        """Render a subtle glow effect behind the blob."""
        import pygame

        t = time.monotonic() - self._t0
        breath = 1.0 + 0.06 * math.sin(t * 1.8)

        if self.state == BlobState.LISTENING:
            breath = 1.15 + 0.1 * self.amplitude
        elif self.state == BlobState.SPEAKING:
            breath = 1.05 + 0.12 * self.amplitude

        glow_r = int(self.base_radius * breath * 1.6)
        glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)

        # Concentric rings for glow effect
        for ring in range(3):
            r = glow_r - ring * (glow_r // 4)
            alpha = max(5, glow_alpha - ring * 10)
            pygame.draw.circle(
                glow_surf,
                (*color, alpha),
                (glow_r, glow_r),
                max(1, r),
            )

        surface.blit(
            glow_surf,
            (self.cx - glow_r, self.cy - glow_r),
            special_flags=pygame.BLEND_RGBA_ADD if surface.get_flags() & pygame.SRCALPHA else 0,
        )
