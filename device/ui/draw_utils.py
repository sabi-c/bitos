"""BITOS pixel drawing helpers for status and app icons."""

from __future__ import annotations

import math
import pygame


def draw_wifi(surf: pygame.Surface, x: int, y: int, w: int, h: int, color) -> None:
    """Draw 3 wifi arcs + center dot."""
    lw = max(1, round(w / 10))
    cx = int(x + w * 0.5)
    for radius_frac, y_frac in [(0.12, 0.9), (0.30, 0.65), (0.50, 0.40)]:
        cy = int(y + h * y_frac)
        r = max(2, int(w * radius_frac))
        rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
        pygame.draw.arc(surf, color, rect, math.pi * 1.15, math.pi * 1.85, lw)
    pygame.draw.circle(surf, color, (cx, int(y + h * 0.9)), max(1, int(w * 0.08)))


def draw_battery(surf: pygame.Surface, x: int, y: int, w: int, h: int, color) -> None:
    """Draw battery outline + terminal nub + fill amount."""
    pygame.draw.rect(surf, color, (x, y + int(h * 0.2), int(w * 0.85), int(h * 0.6)), 2)
    pygame.draw.rect(surf, color, (x + int(w * 0.85), y + int(h * 0.35), max(1, int(w * 0.15)), int(h * 0.3)))
    pygame.draw.rect(surf, color, (x + int(w * 0.06), y + int(h * 0.3), int(w * 0.55), int(h * 0.4)))


def draw_signal(surf: pygame.Surface, x: int, y: int, w: int, h: int, color) -> None:
    """Draw 4 increasing signal bars."""
    bars = [(0.0, 0.7, 0.2, 0.3), (0.25, 0.5, 0.2, 0.5), (0.50, 0.3, 0.2, 0.7), (0.75, 0.1, 0.2, 0.9)]
    for lx, ly, lw, lh in bars:
        pygame.draw.rect(surf, color, (x + int(lx * w), y + int(ly * h), max(1, int(lw * w)), max(1, int(lh * h))))


def draw_lock(surf: pygame.Surface, x: int, y: int, w: int, h: int, color) -> None:
    """Draw padlock icon."""
    lw = max(1, round(w / 12))
    pygame.draw.rect(surf, color, (x + int(w * 0.15), y + int(h * 0.45), int(w * 0.7), int(h * 0.5)), lw)
    cx = x + w // 2
    cy = y + int(h * 0.45)
    r = max(2, int(w * 0.25))
    rect = pygame.Rect(cx - r, cy - r, 2 * r, 2 * r)
    pygame.draw.arc(surf, color, rect, math.pi, 0, lw)
    pygame.draw.rect(surf, color, (x + int(w * 0.45), y + int(h * 0.62), max(1, int(w * 0.1)), int(h * 0.2)))


def draw_mail(surf: pygame.Surface, x: int, y: int, w: int, h: int, color) -> None:
    """Draw envelope icon."""
    lw = max(1, round(w / 14))
    pygame.draw.rect(surf, color, (x + int(w * 0.05), y + int(h * 0.2), int(w * 0.9), int(h * 0.65)), lw)
    pts = [
        (x + int(w * 0.05), y + int(h * 0.2)),
        (x + int(w * 0.5), y + int(h * 0.6)),
        (x + int(w * 0.95), y + int(h * 0.2)),
    ]
    pygame.draw.lines(surf, color, False, pts, lw)


def draw_settings(surf: pygame.Surface, x: int, y: int, w: int, h: int, color) -> None:
    """Draw gear icon."""
    lw = max(1, round(w / 12))
    cx, cy = x + w // 2, y + h // 2
    r = int(h * 0.25)
    pygame.draw.circle(surf, color, (cx, cy), r, lw)
    for i in range(8):
        a = i * math.pi * 2 / 8
        px = int(cx + h * 0.42 * math.cos(a))
        py = int(cy + h * 0.42 * math.sin(a))
        pygame.draw.circle(surf, color, (px, py), max(2, int(w * 0.06)))


def draw_ai(surf: pygame.Surface, x: int, y: int, w: int, h: int, color) -> None:
    """Draw AI/chat icon."""
    lw = max(1, w // 12)
    pygame.draw.rect(surf, color, (x + int(w * 0.1), y + int(h * 0.1), int(w * 0.8), int(h * 0.65)), lw)
    for dx in [0.3, 0.5, 0.7]:
        pygame.draw.circle(surf, color, (x + int(w * dx), y + int(h * 0.42)), max(1, int(w * 0.05)))
    pygame.draw.line(surf, color, (x + int(w * 0.35), y + int(h * 0.75)), (x + int(w * 0.3), y + int(h * 0.9)), lw)
    pygame.draw.line(surf, color, (x + int(w * 0.65), y + int(h * 0.75)), (x + int(w * 0.7), y + int(h * 0.9)), lw)
