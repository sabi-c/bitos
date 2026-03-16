"""Rounded corner mask — draws black corners to match display bezel.

Pre-renders a transparent mask with black rounded corners on init.
Call mask.apply(surface) as the final render step each frame.
"""

import pygame

# Corner radius matching the ST7789 display bezel
CORNER_RADIUS = 8


class CornerMask:
    """Pre-rendered corner mask overlay."""

    def __init__(self, width: int = 240, height: int = 280, radius: int = CORNER_RADIUS):
        self._mask = pygame.Surface((width, height), pygame.SRCALPHA)
        self._mask.fill((0, 0, 0, 0))  # fully transparent

        # Draw black filled corners by drawing black rects and then
        # cutting out the rounded area with circles
        r = radius
        w, h = width, height
        black = (0, 0, 0, 255)

        # Top-left corner
        pygame.draw.rect(self._mask, black, (0, 0, r, r))
        pygame.draw.circle(self._mask, (0, 0, 0, 0), (r, r), r)

        # Top-right corner
        pygame.draw.rect(self._mask, black, (w - r, 0, r, r))
        pygame.draw.circle(self._mask, (0, 0, 0, 0), (w - r, r), r)

        # Bottom-left corner
        pygame.draw.rect(self._mask, black, (0, h - r, r, r))
        pygame.draw.circle(self._mask, (0, 0, 0, 0), (r, h - r), r)

        # Bottom-right corner
        pygame.draw.rect(self._mask, black, (w - r, h - r, r, r))
        pygame.draw.circle(self._mask, (0, 0, 0, 0), (w - r, h - r), r)

    def apply(self, surface: pygame.Surface) -> None:
        """Blit the corner mask onto the surface."""
        surface.blit(self._mask, (0, 0))
