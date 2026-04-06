"""
ToolStatusAnimation — procedural 16x16 pixel-art icons for tool status.
Each icon is drawn pixel-by-pixel using pygame.draw.rect on a tiny surface.
"""
from __future__ import annotations

import pygame

from .animator import StepAnimator
from .tokens import WHITE, BLACK, DIM2, DIM3

# ── Icon mapping ──────────────────────────────────────────────────

_ICON_RULES: list[tuple[str, str]] = [
    ("think", "brain"),
    ("search", "magnifier"),
    ("analy", "gear"),
    ("process", "dots"),
    ("build", "pencil"),
    ("calendar", "calendar"),
    ("email", "envelope"),
    ("mail", "envelope"),
    ("web", "globe"),
    ("task", "checkbox"),
    ("remember", "thought"),
    ("memory", "thought"),
]

_FALLBACK_ICON = "dots"


def icon_for_status(status: str) -> str:
    """Return icon name for a status string (case-insensitive substring match)."""
    low = status.lower()
    for substring, icon in _ICON_RULES:
        if substring in low:
            return icon
    return _FALLBACK_ICON


# ── Pixel drawing helper ─────────────────────────────────────────

def _px(surf: pygame.Surface, x: int, y: int, color=WHITE):
    """Draw a single pixel on a surface."""
    pygame.draw.rect(surf, color, (x, y, 1, 1))


# ── Procedural icon drawers ──────────────────────────────────────
# Each function receives (surf_16x16, frame 0-3) and draws WHITE on BLACK.

def _draw_dots(surf: pygame.Surface, frame: int):
    """Sequential fill: 1-4 dots."""
    n = frame + 1
    for i in range(n):
        cx = 3 + i * 3
        pygame.draw.rect(surf, WHITE, (cx, 7, 2, 2))


def _draw_gear(surf: pygame.Surface, frame: int):
    """Rotating gear — circle with teeth that shift each frame."""
    # Center hub
    pygame.draw.rect(surf, WHITE, (6, 6, 4, 4))
    # Teeth at 4 positions, offset by frame
    teeth = [
        (7, 2, 2, 3),   # top
        (11, 7, 3, 2),  # right
        (7, 11, 2, 3),  # bottom
        (2, 7, 3, 2),   # left
    ]
    for i, rect in enumerate(teeth):
        idx = (i + frame) % 4
        color = WHITE if idx < 3 else DIM3
        pygame.draw.rect(surf, color, rect)


def _draw_magnifier(surf: pygame.Surface, frame: int):
    """Magnifying glass with sweep highlight."""
    # Lens circle (approximated)
    lens_pixels = [
        (5, 3), (6, 3), (7, 3), (8, 3),
        (4, 4), (9, 4),
        (3, 5), (10, 5),
        (3, 6), (10, 6),
        (3, 7), (10, 7),
        (3, 8), (10, 8),
        (4, 9), (9, 9),
        (5, 10), (6, 10), (7, 10), (8, 10),
    ]
    for px, py in lens_pixels:
        _px(surf, px, py)
    # Handle
    for i in range(3):
        _px(surf, 10 + i, 10 + i)
        _px(surf, 11 + i, 10 + i)
    # Sweep highlight — a bright spot that moves around the lens
    highlights = [
        [(5, 5), (6, 5)],
        [(8, 5), (9, 6)],
        [(9, 8), (8, 9)],
        [(5, 9), (4, 8)],
    ]
    for px, py in highlights[frame % 4]:
        _px(surf, px, py, DIM2)


def _draw_brain(surf: pygame.Surface, frame: int):
    """Brain with pulse animation — outline shifts brightness."""
    # Left hemisphere
    left = [
        (3, 4), (4, 3), (5, 3), (6, 3),
        (2, 5), (2, 6), (2, 7), (2, 8),
        (3, 9), (4, 10), (5, 10), (6, 10),
        (3, 5), (4, 4), (5, 4),
        (3, 7), (4, 8), (5, 8),
        (4, 6), (5, 6),
    ]
    # Right hemisphere
    right = [
        (9, 3), (10, 3), (11, 4),
        (12, 5), (12, 6), (12, 7), (12, 8),
        (11, 9), (10, 10), (9, 10), (8, 10),
        (11, 5), (10, 4), (9, 4),
        (11, 7), (10, 8), (9, 8),
        (10, 6), (9, 6),
    ]
    # Center divide
    center = [(7, 3), (7, 4), (7, 5), (7, 6), (7, 7), (7, 8), (7, 9), (7, 10)]

    pulse_colors = [WHITE, DIM2, DIM3, DIM2]
    color = pulse_colors[frame % 4]

    for px, py in left:
        _px(surf, px, py, color)
    for px, py in right:
        _px(surf, px, py, color)
    for px, py in center:
        _px(surf, px, py, WHITE)


def _draw_pencil(surf: pygame.Surface, frame: int):
    """Writing pencil with bobbing tip."""
    offset = [0, -1, 0, 1][frame % 4]
    # Pencil body (diagonal)
    for i in range(8):
        _px(surf, 4 + i, 3 + i + offset)
        _px(surf, 5 + i, 3 + i + offset)
    # Tip
    _px(surf, 3, 11 + offset)
    # Eraser end
    pygame.draw.rect(surf, DIM2, (11, 3 + offset, 2, 2))


def _draw_calendar(surf: pygame.Surface, frame: int):
    """Calendar icon with blinking date."""
    # Outline
    pygame.draw.rect(surf, WHITE, (2, 3, 12, 11), 1)
    # Header bar
    pygame.draw.rect(surf, WHITE, (2, 3, 12, 3))
    # Rings
    _px(surf, 5, 2)
    _px(surf, 10, 2)
    # Date number "15" — blinks
    if frame % 4 != 3:
        # "1"
        _px(surf, 5, 9)
        _px(surf, 5, 10)
        _px(surf, 5, 11)
        # "5"
        pygame.draw.rect(surf, WHITE, (8, 9, 3, 1))
        _px(surf, 8, 10)
        pygame.draw.rect(surf, WHITE, (8, 10, 3, 1))
        _px(surf, 10, 11)
        pygame.draw.rect(surf, WHITE, (8, 11, 3, 1))


def _draw_envelope(surf: pygame.Surface, frame: int):
    """Envelope with flap open/close."""
    # Body
    pygame.draw.rect(surf, WHITE, (2, 6, 12, 7), 1)
    # V-lines inside
    for i in range(5):
        _px(surf, 3 + i, 7 + i)
        _px(surf, 13 - i, 7 + i)
    # Flap — opens over frames
    flap_heights = [0, 1, 2, 1]
    fh = flap_heights[frame % 4]
    pygame.draw.rect(surf, WHITE, (2, 6 - fh, 12, 1))
    if fh > 0:
        for i in range(fh):
            _px(surf, 3 + i, 5 - i)
            _px(surf, 12 - i, 5 - i)


def _draw_globe(surf: pygame.Surface, frame: int):
    """Globe with rotating meridian."""
    # Circle outline (approximated)
    circle = [
        (6, 2), (7, 2), (8, 2), (9, 2),
        (5, 3), (10, 3),
        (4, 4), (11, 4),
        (3, 5), (12, 5),
        (3, 6), (12, 6),
        (3, 7), (12, 7),
        (3, 8), (12, 8),
        (3, 9), (12, 9),
        (4, 10), (11, 10),
        (5, 11), (10, 11),
        (6, 12), (7, 12), (8, 12), (9, 12),
    ]
    for px, py in circle:
        _px(surf, px, py)
    # Equator
    for x in range(4, 12):
        _px(surf, x, 7)
    # Meridian shifts with frame
    meridian_x = [7, 9, 8, 6][frame % 4]
    for y in range(3, 12):
        _px(surf, meridian_x, y)


def _draw_checkbox(surf: pygame.Surface, frame: int):
    """Checkbox with check drawing in over 4 frames."""
    # Box
    pygame.draw.rect(surf, WHITE, (3, 3, 10, 10), 1)
    # Check mark draws in progressively
    check_pixels = [
        [(5, 8)],
        [(5, 8), (6, 9)],
        [(5, 8), (6, 9), (7, 10)],
        [(5, 8), (6, 9), (7, 10), (8, 9), (9, 8), (10, 7), (11, 6)],
    ]
    for px, py in check_pixels[min(frame, 3)]:
        _px(surf, px, py)
        _px(surf, px, py - 1)  # thicken


def _draw_thought(surf: pygame.Surface, frame: int):
    """Thought bubble with pulse."""
    # Bubble
    bubble = [
        (4, 2), (5, 2), (6, 2), (7, 2), (8, 2), (9, 2), (10, 2),
        (3, 3), (11, 3),
        (2, 4), (12, 4),
        (2, 5), (12, 5),
        (2, 6), (12, 6),
        (3, 7), (11, 7),
        (4, 8), (5, 8), (6, 8), (7, 8), (8, 8), (9, 8), (10, 8),
    ]
    pulse_colors = [WHITE, DIM2, DIM3, DIM2]
    color = pulse_colors[frame % 4]
    for px, py in bubble:
        _px(surf, px, py, color)
    # Trail dots
    _px(surf, 6, 10, WHITE)
    _px(surf, 5, 12, WHITE)


# ── Icon registry ────────────────────────────────────────────────

_ICON_DRAWERS = {
    "dots": _draw_dots,
    "gear": _draw_gear,
    "magnifier": _draw_magnifier,
    "brain": _draw_brain,
    "pencil": _draw_pencil,
    "calendar": _draw_calendar,
    "envelope": _draw_envelope,
    "globe": _draw_globe,
    "checkbox": _draw_checkbox,
    "thought": _draw_thought,
}

# ── Main component ───────────────────────────────────────────────

_ICON_SIZE = 16


class ToolStatusAnimation:
    """Animated tool-status indicator with procedural pixel-art icon + label."""

    def __init__(self):
        self._status: str | None = None
        self._icon_name: str | None = None
        self._animator: StepAnimator | None = None
        self._icon_surf = pygame.Surface((_ICON_SIZE, _ICON_SIZE))
        self._font: pygame.font.Font | None = None

    # ── Public API ────────────────────────────────────────────

    def set_status(self, status: str) -> None:
        """Set or update the current status text. Resets animation if icon changes."""
        new_icon = icon_for_status(status)
        if new_icon != self._icon_name:
            self._icon_name = new_icon
            self._animator = StepAnimator(total_steps=4, duration_s=1.2, loop=True)
        self._status = status

    def clear(self) -> None:
        """Hide the animation."""
        self._status = None
        self._icon_name = None
        self._animator = None

    @property
    def active(self) -> bool:
        """Whether the animation is currently showing."""
        return self._status is not None

    def update(self, dt_ms: float) -> None:
        """Advance animation by *dt_ms* milliseconds."""
        if self._animator is not None:
            self._animator.update(dt_ms / 1000.0)

    def render(self, surface: pygame.Surface, x: int, y: int) -> int:
        """Draw icon + label at (x, y). Returns total height used."""
        if not self.active or self._animator is None:
            return 0

        frame = self._animator.step

        # Draw icon onto small surface
        self._icon_surf.fill(BLACK)
        drawer = _ICON_DRAWERS.get(self._icon_name, _draw_dots)
        drawer(self._icon_surf, frame)
        surface.blit(self._icon_surf, (x, y))

        # Label with animated trailing dots
        if self._font is None:
            self._font = pygame.font.Font(None, 14)

        dot_count = (frame % 3) + 1
        label = (self._status or "") + "." * dot_count
        text_surf = self._font.render(label, False, WHITE)
        surface.blit(text_surf, (x + _ICON_SIZE + 4, y + 2))

        return _ICON_SIZE
