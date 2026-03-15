"""BITOS Boot screen with diagnostics sequencing and gated readiness."""
from __future__ import annotations

import os
import subprocess
import threading
import time
import urllib.request
import logging

import pygame

logger = logging.getLogger(__name__)

from screens.base import BaseScreen
from display.tokens import (
    BLACK,
    WHITE,
    DIM2,
    DIM3,
    DIM4,
    PHYSICAL_W,
    PHYSICAL_H,
    FONT_PATH,
    STATUS_BAR_H,
)
from display.animator import orb_rotate, blink_cursor


logger = logging.getLogger(__name__)


class BootDiagnostics:
    CHECKS = ["display", "button", "audio", "network", "api_key", "battery"]

    def __init__(self):
        self.results: dict[str, bool | None] = {}
        self._lock = threading.Lock()

    def run_async(self):
        """Start all checks in background threads."""
        for idx, check in enumerate(self.CHECKS):
            threading.Thread(target=self._run_check, args=(check, idx), daemon=True).start()

    def _run_check(self, name: str, idx: int):
        try:
            result = bool(getattr(self, f"_check_{name}")())
            with self._lock:
                self.results[name] = result
        except Exception as exc:
            logger.warning("boot_check_failed check=%s error=%s", name, exc)
            with self._lock:
                self.results[name] = False

    def _check_display(self):
        return True

    def _check_button(self):
        mode = os.environ.get("BITOS_BUTTON", "keyboard")
        if mode != "gpio":
            return True
        try:
            from hardware.whisplay_board import get_board

            board = get_board()
            return board is not None
        except Exception as exc:
            logger.warning("boot_button_board_check_failed error=%s", exc)
            return False

    def _check_audio(self):
        mode = os.environ.get("BITOS_AUDIO", "mock")
        if mode == "mock":
            return True
        r = subprocess.run(["aplay", "-l"], capture_output=True, timeout=1, check=False)
        return r.returncode == 0

    def _check_network(self):
        base = os.environ.get("SERVER_URL") or os.environ.get("BITOS_SERVER_URL", "http://localhost:8000")
        url = f"{base.rstrip('/')}/health"
        with urllib.request.urlopen(url, timeout=1):
            return True

    def _check_api_key(self):
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        return bool(key and not key.startswith("test-"))

    def _check_battery(self):
        mode = os.environ.get("BITOS_BATTERY", "mock")
        if mode == "mock":
            return True
        try:
            from device.power import BatteryMonitor

            status = BatteryMonitor().get_status()
            return bool(status)
        except Exception as exc:
            logger.warning("boot_battery_check_failed error=%s", exc)
            return False


    def ensure_critical_results(self) -> None:
        """Fill any missing critical results synchronously to avoid indefinite wait."""
        for name in ("display", "button"):
            with self._lock:
                if name in self.results:
                    continue
            try:
                value = bool(getattr(self, f"_check_{name}")())
            except Exception as exc:
                logger.warning("boot_critical_check_failed check=%s error=%s", name, exc)
                value = False
            with self._lock:
                self.results[name] = value

    def all_critical_passed(self) -> bool:
        """Display + button are true blockers for boot progression."""
        critical = ["display", "button"]
        with self._lock:
            return all(self.results.get(c) for c in critical)

    def is_complete(self) -> bool:
        with self._lock:
            return len(self.results) == len(self.CHECKS)


class BootScreen(BaseScreen):
    """Boot animation: rotating orbs + diagnostics grid."""

    _owns_status_bar: bool = True

    _LABELS = {
        "display": "DISPLAY",
        "button": "BUTTON",
        "audio": "AUDIO",
        "network": "NETWORK",
        "api_key": "API KEY",
        "battery": "BATTERY",
    }

    def __init__(self, on_complete=None, startup_health: dict | None = None, health_check=None):
        self._on_complete = on_complete
        self._startup_health = startup_health if startup_health is not None else {}
        self._health_lock = threading.Lock()
        self._health_check = health_check
        self._orb_anim = orb_rotate()
        self._cursor_anim = blink_cursor()
        self._elapsed = 0.0
        self._auto_advance_time = 8.0
        self._done = False
        self._diagnostics = BootDiagnostics()
        self._diagnostics.run_async()

        try:
            self._font = pygame.font.Font(FONT_PATH, 32)
        except FileNotFoundError:
            self._font = pygame.font.SysFont("monospace", 32)

        try:
            self._status_font = pygame.font.Font(FONT_PATH, 10)
        except FileNotFoundError:
            self._status_font = pygame.font.SysFont("monospace", 10)

        if self._health_check:
            threading.Thread(target=self._run_health_check, daemon=True).start()

    def update(self, dt: float):
        if self._done:
            return

        self._elapsed += dt
        self._orb_anim.update(dt)
        self._cursor_anim.update(dt)

        if self._elapsed >= self._auto_advance_time:
            self._diagnostics.ensure_critical_results()
            if self._diagnostics.all_critical_passed():
                self._advance()

    def handle_action(self, action: str):
        if not self._done:
            logger.info("[Boot] action=%s → advance", action)
            self._advance()

    def handle_input(self, event: pygame.event.Event):
        if self._done:
            return
        if event.type == pygame.KEYDOWN and self._diagnostics.all_critical_passed():
            self._advance()

    def handle_action(self, action: str):
        if self._done:
            return
        if action in {"SHORT_PRESS", "LONG_PRESS"}:
            self._advance()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        cx, cy = PHYSICAL_W // 2, PHYSICAL_H // 2 - 66
        orb_size = 4

        orbs = [
            (cx + 24, cy),
            (cx + 17, cy - 17),
            (cx, cy - 24),
            (cx - 17, cy - 17),
            (cx - 24, cy),
            (cx - 17, cy + 17),
            (cx, cy + 24),
            (cx + 17, cy + 17),
        ]
        step = self._orb_anim.step % 8

        orb_colors = [WHITE, DIM2, DIM3, DIM4]
        for i in range(4):
            pos_idx = (step + i * 2) % 8
            ox, oy = orbs[pos_idx]
            color = orb_colors[i]
            pygame.draw.rect(surface, color, (ox - orb_size // 2, oy - orb_size // 2, orb_size, orb_size))

        text_surface = self._font.render("BITOS", False, WHITE)
        text_x = (PHYSICAL_W - text_surface.get_width()) // 2
        text_y = cy + 40
        surface.blit(text_surface, (text_x, text_y))

        if self._cursor_anim.step == 0:
            cursor_x = text_x + text_surface.get_width() + 2
            cursor_w = 32
            cursor_h = 32
            pygame.draw.rect(surface, WHITE, (cursor_x, text_y, cursor_w, cursor_h))

        checks_start_y = text_y + self._font.get_height() + 8
        self._render_checks(surface, checks_start_y)

        self._render_api_key_warning(surface)

        status_surface = self._status_font.render(self._status_copy(), False, DIM2 if self._diagnostics.results.get("api_key", True) else WHITE)
        status_x = (PHYSICAL_W - status_surface.get_width()) // 2
        surface.blit(status_surface, (status_x, PHYSICAL_H - STATUS_BAR_H))

    def _render_api_key_warning(self, surface: pygame.Surface) -> None:
        if self._diagnostics.results.get("api_key", True):
            return
        warning_h = 14
        warning_y = PHYSICAL_H - STATUS_BAR_H - warning_h - 2
        pygame.draw.rect(surface, DIM4, (8, warning_y, PHYSICAL_W - 16, warning_h))
        warning = self._status_font.render("WARNING: API KEY MISSING", False, WHITE)
        warning_x = (PHYSICAL_W - warning.get_width()) // 2
        surface.blit(warning, (warning_x, warning_y + 2))

    def _render_checks(self, surface: pygame.Surface, start_y: int) -> None:
        col_x = [26, 126]
        row_y = [start_y, start_y + 18, start_y + 36]
        checks = ["display", "button", "audio", "network", "api_key", "battery"]
        for idx, name in enumerate(checks):
            show_now = self._elapsed >= idx * 0.5
            result = self._diagnostics.results.get(name) if show_now else None
            if result is None:
                mark = "…"
                color = DIM4
            else:
                mark = "✓" if result else "✕"
                color = WHITE if result else DIM2
            label = self._LABELS[name]
            col = idx % 2
            row = idx // 2
            surf = self._status_font.render(f"{label:<8} {mark}", False, color)
            surface.blit(surf, (col_x[col], row_y[row]))

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
                with self._health_lock:
                    self._startup_health.update(result)
        except Exception as exc:
            logger.warning("boot_health_check_failed error=%s", exc)
            with self._health_lock:
                self._startup_health.update({"backend": False})

    def _status_copy(self) -> str:
        if not self._diagnostics.results.get("api_key", True):
            if int(time.time() * 2) % 2 == 0:
                return "API KEY MISSING — add to /etc/bitos/secrets"
            return "SHORT/LONG TO CONTINUE"

        if self._diagnostics.is_complete() and self._diagnostics.all_critical_passed():
            return "READY"

        with self._health_lock:
            backend_status = self._startup_health.get("backend")
        if backend_status is None:
            return "CHECKING..."
        if backend_status:
            return "NETWORK OK"
        return "OFFLINE MODE"
