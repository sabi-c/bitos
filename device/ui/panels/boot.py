"""Boot screen — pixel orbs animation, BITOS title, tap hint.

Renders into full 240x280 surface (no sidebar on boot).
Matches bitos-nav-v2.html #bootView specification.
"""

import math

import pygame

from device.ui.fonts import get_font

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY_333 = (51, 51, 51)
GRAY_222 = (34, 34, 34)
GRAY_1A = (26, 26, 26)
GRAY_111 = (17, 17, 17)

SCREEN_W = 240
SCREEN_H = 280


class BootPanel:
    """Full-screen boot animation. Renders onto 240x280 surface."""

    def __init__(self):
        self._frame = 0

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)

        cx, cy = SCREEN_W // 2, SCREEN_H // 2 - 30
        radius = 36
        t = self._frame * 0.04
        pix = 2

        # 4 orbiting pixel orbs
        for i in range(4):
            angle = t + i * math.pi / 2
            ox = int(cx + radius * math.cos(angle))
            oy = int(cy + radius * math.sin(angle))

            # Main orb (pixelated circle)
            for py in range(-4, 5):
                for px in range(-4, 5):
                    if px * px + py * py <= 16:
                        pygame.draw.rect(surface, WHITE,
                                         (ox + px * pix, oy + py * pix, pix, pix))

            # Dim trail
            trail_angle = angle - 0.3
            tx = int(cx + radius * math.cos(trail_angle))
            ty = int(cy + radius * math.sin(trail_angle))
            for py in range(-3, 4):
                for px in range(-3, 4):
                    if px * px + py * py <= 9:
                        pygame.draw.rect(surface, GRAY_333,
                                         (tx + px * pix, ty + py * pix, pix, pix))

        # Center dot
        pygame.draw.rect(surface, GRAY_222, (cx - 4, cy - 4, 8, 8))
        pygame.draw.rect(surface, WHITE, (cx - 2, cy - 2, 4, 4))

        # "BITOS" title with blinking cursor
        font_9 = get_font(9)
        title_surf = font_9.render("BITOS", False, WHITE)
        title_y = cy + radius + 30
        surface.blit(title_surf, ((SCREEN_W - title_surf.get_width()) // 2, title_y))

        # Block cursor (blinking)
        if (self._frame // 12) % 2 == 0:
            cursor_x = (SCREEN_W + title_surf.get_width()) // 2 + 2
            pygame.draw.rect(surface, WHITE, (cursor_x, title_y, 6, 10))

        # Version text
        font_4 = get_font(5)
        ver_surf = font_4.render("v1.0 \u00b7 MONOCHROME AI DEVICE", False, GRAY_1A)
        surface.blit(ver_surf, ((SCREEN_W - ver_surf.get_width()) // 2, title_y + 18))

        # Bottom hint
        hint_surf = font_4.render("TAP BUTTON TO BOOT", False, GRAY_111)
        surface.blit(hint_surf, ((SCREEN_W - hint_surf.get_width()) // 2, SCREEN_H - 14))

        self._frame += 1
