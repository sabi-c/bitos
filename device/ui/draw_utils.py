"""
BITOS Pixel Icon Library
Ported from 1bit-system-screens.html canvas 2D drawing functions.
All icons use the same signature: draw_X(surf, x, y, w, h, color)
"""

import math

import pygame


def draw_wifi(surf, x, y, w, h, color):
    """3 arcs + center dot."""
    for r_frac, y_frac in [(0.12, 0.9), (0.30, 0.65), (0.50, 0.40)]:
        cx = int(x + w * 0.5)
        cy = int(y + h * y_frac)
        r = max(2, int(w * r_frac))
        lw = max(1, int(w / 10))
        rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
        pygame.draw.arc(surf, color, rect, math.pi * 0.15, math.pi * 0.85, lw)
    pygame.draw.circle(surf, color, (int(x + w * 0.5), int(y + h * 0.9)), max(1, int(w * 0.08)))


def draw_battery(surf, x, y, w, h, color):
    """Outline rect + nub + fill bar."""
    pygame.draw.rect(surf, color, (x, y + int(h * 0.2), int(w * 0.85), int(h * 0.6)), 2)
    pygame.draw.rect(surf, color, (x + int(w * 0.85), y + int(h * 0.35), int(w * 0.15), int(h * 0.3)))
    pygame.draw.rect(surf, color, (x + int(w * 0.06), y + int(h * 0.3), int(w * 0.55), int(h * 0.4)))


def draw_signal(surf, x, y, w, h, color):
    """4 bars of increasing height."""
    for lx, ly in [(0.0, 0.7), (0.3, 0.5), (0.6, 0.3), (0.9, 0.1)]:
        pygame.draw.rect(surf, color, (x + int(lx * w), y + int(ly * h), int(w * 0.25), int(h * (1.0 - ly))))


def draw_lock(surf, x, y, w, h, color):
    """Padlock body + shackle arc + keyhole."""
    lw = max(1, int(w / 12))
    pygame.draw.rect(surf, color, (x + int(w * 0.15), y + int(h * 0.45), int(w * 0.7), int(h * 0.5)), lw)
    cx = x + w // 2
    cy = y + int(h * 0.45)
    r = int(w * 0.25)
    rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
    pygame.draw.arc(surf, color, rect, 0, math.pi, lw)
    pygame.draw.rect(surf, color, (x + int(w * 0.45), y + int(h * 0.62), int(w * 0.1), int(h * 0.2)))


def draw_mail(surf, x, y, w, h, color):
    """Envelope rect + V flap."""
    lw = max(1, int(w / 14))
    pygame.draw.rect(surf, color, (x + int(w * 0.05), y + int(h * 0.2), int(w * 0.9), int(h * 0.65)), lw)
    pts = [
        (x + int(w * 0.05), y + int(h * 0.2)),
        (x + w // 2, y + int(h * 0.6)),
        (x + int(w * 0.95), y + int(h * 0.2)),
    ]
    pygame.draw.lines(surf, color, False, pts, lw)


def draw_settings(surf, x, y, w, h, color):
    """Gear: circle + 8 dot teeth."""
    cx, cy = x + w // 2, y + h // 2
    r = int(h * 0.25)
    lw = max(1, int(w / 12))
    pygame.draw.circle(surf, color, (cx, cy), r, lw)
    for i in range(8):
        a = i * math.pi * 2 / 8
        px = int(cx + h * 0.42 * math.cos(a))
        py = int(cy + h * 0.42 * math.sin(a))
        pygame.draw.circle(surf, color, (px, py), max(2, int(w * 0.06)))


def draw_ai(surf, x, y, w, h, color):
    """Chat bubble + 3 dots + 2 legs."""
    lw = max(1, int(w / 12))
    pygame.draw.rect(surf, color, (x + int(w * 0.1), y + int(h * 0.1), int(w * 0.8), int(h * 0.65)), lw)
    for dx in (0.3, 0.5, 0.7):
        pygame.draw.circle(surf, color, (x + int(w * dx), y + int(h * 0.42)), max(1, int(w * 0.05)))
    pygame.draw.line(surf, color, (x + int(w * 0.35), y + int(h * 0.75)), (x + int(w * 0.3), y + int(h * 0.9)), lw)
    pygame.draw.line(surf, color, (x + int(w * 0.65), y + int(h * 0.75)), (x + int(w * 0.7), y + int(h * 0.9)), lw)
