"""BITOS Focus panel with button-first timer controls."""
from __future__ import annotations

import pygame

from display.theme import load_ui_font, merge_runtime_ui_settings
from display.tokens import BLACK, DIM1, DIM2, DIM3, HAIRLINE, PHYSICAL_H, PHYSICAL_W, WHITE
from screens.base import BaseScreen
from screens.components import NavItem, VerticalNavController


class FocusPanel(BaseScreen):
    """Minimal focus timer experience for Phase 4 shell breadth."""

    def __init__(self, on_back=None, ui_settings: dict | None = None, duration_seconds: int = 25 * 60):
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)

        self._default_duration = max(60, int(duration_seconds))
        self._remaining_seconds = self._default_duration
        self._is_running = False
        self._countdown_accum = 0.0

        self._nav = VerticalNavController(
            [
                NavItem(key="start_pause", label="START", status="READY", action=self._toggle_running),
                NavItem(key="reset", label="RESET", status="ZERO", action=self._reset_timer),
                NavItem(key="back", label="BACK", status="HOME", action=self._go_back),
            ]
        )

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._nav.activate_focused()
        elif action in {"DOUBLE_PRESS", "LONG_PRESS"}:
            self._nav.move(1)
        elif action == "TRIPLE_PRESS":
            self._nav.move(-1)

    def handle_input(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            return

        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._nav.activate_focused()
        elif event.key in (pygame.K_DOWN, pygame.K_j):
            self._nav.move(1)
        elif event.key in (pygame.K_UP, pygame.K_k):
            self._nav.move(-1)

    def update(self, dt: float):
        if not self._is_running:
            return

        self._countdown_accum += max(0.0, dt)
        elapsed = int(self._countdown_accum)
        if elapsed <= 0:
            return
        self._countdown_accum -= elapsed

        self._remaining_seconds = max(0, self._remaining_seconds - elapsed)
        if self._remaining_seconds <= 0:
            self._is_running = False

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        title = self._font_title.render("FOCUS", False, WHITE)
        surface.blit(title, (8, 8))
        pygame.draw.line(surface, HAIRLINE, (0, 24), (PHYSICAL_W, 24))

        timer_text = self._timer_copy()
        timer_surface = self._font_title.render(timer_text, False, WHITE)
        timer_x = (PHYSICAL_W - timer_surface.get_width()) // 2
        surface.blit(timer_surface, (timer_x, 48))

        mode = "RUNNING" if self._is_running else "PAUSED"
        mode_surface = self._font_small.render(mode, False, DIM1 if self._is_running else DIM2)
        mode_x = (PHYSICAL_W - mode_surface.get_width()) // 2
        surface.blit(mode_surface, (mode_x, 68))

        self._sync_nav_labels()
        y = 100
        for idx, item in enumerate(self._nav.items):
            row = self._font_body.render(item.label, False, WHITE)
            status = self._font_small.render(item.status, False, DIM2)
            if idx == self._nav.focus_index:
                pygame.draw.rect(surface, WHITE, pygame.Rect(4, y - 2, PHYSICAL_W - 8, 15), width=1)
            surface.blit(row, (8, y))
            surface.blit(status, (PHYSICAL_W - status.get_width() - 8, y + 2))
            pygame.draw.line(surface, HAIRLINE, (8, y + 12), (PHYSICAL_W - 8, y + 12))
            y += 20

        hint = self._font_small.render("SEL SHORT • BACK MENU", False, DIM3)
        surface.blit(hint, (8, PHYSICAL_H - 14))


    def restore_state(self, remaining_seconds: int, is_running: bool):
        self._remaining_seconds = max(0, int(remaining_seconds))
        self._is_running = bool(is_running and self._remaining_seconds > 0)
        self._countdown_accum = 0.0

    @property
    def remaining_seconds(self) -> int:
        return self._remaining_seconds

    @property
    def is_running(self) -> bool:
        return self._is_running

    def _toggle_running(self):
        if self._remaining_seconds <= 0:
            self._remaining_seconds = self._default_duration
        self._is_running = not self._is_running

    def _reset_timer(self):
        self._is_running = False
        self._countdown_accum = 0.0
        self._remaining_seconds = self._default_duration

    def _go_back(self):
        if self._on_back:
            self._on_back()

    def _timer_copy(self) -> str:
        minutes = self._remaining_seconds // 60
        seconds = self._remaining_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def _sync_nav_labels(self):
        items = self._nav.items
        if not items:
            return
        start_item = items[0]
        label = "PAUSE" if self._is_running else "START"
        status = "LIVE" if self._is_running else "READY"
        items[0] = NavItem(
            key=start_item.key,
            label=label,
            status=status,
            enabled=start_item.enabled,
            action=start_item.action,
        )
