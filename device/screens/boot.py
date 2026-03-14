"""
BITOS Boot Screen
4 pixel orbs rotating in 8 steps + "BITOS" text with blinking cursor.
Auto-advances after 3 seconds or any button press.
"""
import math
import threading
import pygame

from screens.base import BaseScreen
from display.tokens import (
    BLACK, WHITE, DIM2, DIM3, DIM4,
    PHYSICAL_W, PHYSICAL_H, FONT_PATH, FONT_SIZES, STATUS_BAR_H
)
from display.animator import StepAnimator, orb_rotate, blink_cursor


class BootScreen(BaseScreen):
    """Boot animation: rotating orbs + BITOS title."""

    def __init__(self, on_complete=None, startup_health: dict | None = None, health_check=None):
        self._on_complete = on_complete
        self._startup_health = startup_health if startup_health is not None else {}
        self._health_check = health_check
        self._orb_anim = orb_rotate()
        self._cursor_anim = blink_cursor()
        self._elapsed = 0.0
        self._auto_advance_time = 3.0
        self._done = False

        # Load font
        try:
            self._font = pygame.font.Font(FONT_PATH, FONT_SIZES["title"])
        except FileNotFoundError:
            self._font = pygame.font.SysFont("monospace", FONT_SIZES["title"])

        try:
            self._status_font = pygame.font.Font(FONT_PATH, FONT_SIZES["small"])
        except FileNotFoundError:
            self._status_font = pygame.font.SysFont("monospace", FONT_SIZES["small"])

        if self._health_check:
            threading.Thread(target=self._run_health_check, daemon=True).start()

    def update(self, dt: float):
        if self._done:
            return

        self._elapsed += dt
        self._orb_anim.update(dt)
        self._cursor_anim.update(dt)

        if self._elapsed >= self._auto_advance_time:
            self._advance()

    def handle_input(self, event: pygame.event.Event):
        if self._done:
            return
        if event.type == pygame.KEYDOWN:
            self._advance()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # ── Draw 4 rotating orbs ──
        cx, cy = PHYSICAL_W // 2, PHYSICAL_H // 2 - 20
        radius = 24
        orb_size = 4
        step = self._orb_anim.step
        angle_offset = (step / 8) * 2 * math.pi

        orb_colors = [WHITE, DIM2, DIM3, DIM4]
        for i in range(4):
            angle = angle_offset + (i * math.pi / 2)
            ox = int(cx + radius * math.cos(angle))
            oy = int(cy + radius * math.sin(angle))
            color = orb_colors[i % len(orb_colors)]
            pygame.draw.rect(surface, color, (ox - orb_size // 2, oy - orb_size // 2, orb_size, orb_size))

        # ── Draw "BITOS" text ──
        text = "BITOS"
        text_surface = self._font.render(text, False, WHITE)
        text_x = (PHYSICAL_W - text_surface.get_width()) // 2
        text_y = cy + 40
        surface.blit(text_surface, (text_x, text_y))

        # ── Blinking cursor ──
        if self._cursor_anim.step == 0:
            cursor_x = text_x + text_surface.get_width() + 2
            cursor_w = FONT_SIZES["title"]
            cursor_h = FONT_SIZES["title"]
            pygame.draw.rect(surface, WHITE, (cursor_x, text_y, cursor_w, cursor_h))

        status_surface = self._status_font.render(self._status_copy(), False, DIM2)
        status_x = (PHYSICAL_W - status_surface.get_width()) // 2
        surface.blit(status_surface, (status_x, PHYSICAL_H - STATUS_BAR_H))

    def _advance(self):
        if self._done:
            return
        self._done = True
        if self._on_complete:
            self._on_complete()

    def _run_health_check(self):
        try:
            result = self._health_check()
            if isinstance(result, dict):
                self._startup_health.update(result)
        except Exception:
            self._startup_health.update({"backend": False})

    def _status_copy(self) -> str:
        backend_status = self._startup_health.get("backend")
        if backend_status is None:
            return "CONNECTING..."
        return "CLAUDE ONLINE ✓" if backend_status else "AI OFFLINE ⚠"
