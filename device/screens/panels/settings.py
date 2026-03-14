# SPRINT: P4-003 — Wire Settings rows to persisted repository values and add picker/detail panels
# READS:  docs/planning/TASK_TRACKER.md, docs/planning/HANDOFF_NEXT_AGENT.md,
#         device/storage/repository.py, device/screens/panels/settings.py,
#         device/main.py, web_preview/server.py, device/screens/manager.py
# WRITES: device/screens/panels/settings.py, device/storage/repository.py,
#         device/main.py, web_preview/server.py, device/screens/manager.py,
#         device/overlays/__init__.py, device/overlays/notification.py,
#         tests/test_settings_wiring.py, tests/test_notification_overlay.py,
#         docs/planning/TASK_TRACKER.md, docs/planning/HANDOFF_NEXT_AGENT.md, README.md
# TESTS:  tests/test_settings_wiring.py, tests/test_notification_overlay.py
"""BITOS Settings panel and picker/detail screens (Phase 4 wiring)."""
from __future__ import annotations

import pygame

from display.theme import load_ui_font, merge_runtime_ui_settings
from overlays import QROverlay
from bluetooth.constants import build_pair_url
from display.tokens import BLACK, DIM2, DIM3, HAIRLINE, PHYSICAL_H, PHYSICAL_W, WHITE
from screens.base import BaseScreen
from screens.components import NavItem, VerticalNavController
from storage.repository import DeviceRepository


class SettingsPanel(BaseScreen):
    """Button-first settings panel with persisted values and long-press actions."""

    def __init__(
        self,
        repository: DeviceRepository,
        on_back=None,
        on_open_model_picker=None,
        on_open_agent_mode=None,
        on_open_sleep_timer=None,
        on_open_about=None,
        on_open_companion_app=None,
        get_ble_address=None,
        on_set_discoverable=None,
        on_push_overlay=None,
        on_dismiss_overlay=None,
        ui_settings: dict | None = None,
    ):
        self._repo = repository
        self._on_back = on_back
        self._on_open_model_picker = on_open_model_picker
        self._on_open_agent_mode = on_open_agent_mode
        self._on_open_sleep_timer = on_open_sleep_timer
        self._on_open_about = on_open_about
        self._on_open_companion_app = on_open_companion_app
        self._get_ble_address = get_ble_address or (lambda: "mock-BT-addr")
        self._on_set_discoverable = on_set_discoverable or (lambda _enabled, _timeout: None)
        self._on_push_overlay = on_push_overlay
        self._on_dismiss_overlay = on_dismiss_overlay

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)

        self._web_search = bool(self._repo.get_setting("web_search", default=True))
        self._memory = bool(self._repo.get_setting("memory", default=True))

        self._nav = VerticalNavController(
            [
                NavItem(key="web_search", label="WEB SEARCH", status="", action=self._toggle_web_search),
                NavItem(key="memory", label="MEMORY", status="", action=self._toggle_memory),
                NavItem(key="ai_model", label="AI MODEL", status="", action=self._open_model_picker),
                NavItem(key="agent_mode", label="AGENT MODE", status="", action=self._open_agent_mode),
                NavItem(key="sleep", label="SLEEP TIMER", status="", action=self._open_sleep_timer),
                NavItem(key="about", label="ABOUT", status="", action=self._open_about),
                NavItem(key="companion", label="COMPANION APP", status="", action=self._open_companion_app),
                NavItem(key="back", label="BACK", status="HOME", action=self._go_back),
            ]
        )

    def handle_action(self, action: str):
        if action == "LONG_PRESS":
            self._nav.activate_focused()
        elif action == "SHORT_PRESS" and self._nav.focused_item and self._nav.focused_item.key == "back":
            self._nav.activate_focused()
        elif action == "DOUBLE_PRESS":
            self._nav.move(1)
        elif action == "TRIPLE_PRESS":
            self._nav.move(-1)

    def handle_input(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_DOWN, pygame.K_j):
            self._nav.move(1)
        elif event.key in (pygame.K_UP, pygame.K_k):
            self._nav.move(-1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._nav.activate_focused()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        title = self._font_title.render("SETTINGS", False, WHITE)
        surface.blit(title, (8, 8))
        pygame.draw.line(surface, HAIRLINE, (0, 24), (PHYSICAL_W, 24))

        ai_model = str(self._repo.get_setting("ai_model", default="claude-sonnet-4-6"))
        agent_mode = str(self._repo.get_setting("agent_mode", default="producer"))
        sleep_sec = int(self._repo.get_setting("sleep_timeout_seconds", default=60))

        statuses = {
            "web_search": "ON" if self._web_search else "OFF",
            "memory": "ON" if self._memory else "OFF",
            "ai_model": _compact_model_label(ai_model),
            "agent_mode": agent_mode[:10].upper(),
            "sleep": f"{sleep_sec}s",
            "about": "INFO",
            "companion": "PAIR",
            "back": "HOME",
        }

        y = 36
        for idx, item in enumerate(self._nav.items):
            status_copy = statuses.get(item.key, item.status)
            row = self._font_body.render(item.label, False, WHITE)
            status = self._font_small.render(status_copy, False, DIM2)
            if idx == self._nav.focus_index:
                pygame.draw.rect(surface, WHITE, pygame.Rect(4, y - 2, PHYSICAL_W - 8, 15), width=1)
            surface.blit(row, (8, y))
            surface.blit(status, (PHYSICAL_W - status.get_width() - 8, y + 2))
            pygame.draw.line(surface, HAIRLINE, (8, y + 12), (PHYSICAL_W - 8, y + 12))
            y += 16

        hint = self._font_small.render("LONG=SELECT • DBL=NEXT", False, DIM3)
        surface.blit(hint, (8, PHYSICAL_H - 14))

    def _toggle_web_search(self):
        self._web_search = not self._web_search
        self._repo.set_setting("web_search", self._web_search)

    def _toggle_memory(self):
        self._memory = not self._memory
        self._repo.set_setting("memory", self._memory)

    def _open_model_picker(self):
        if self._on_open_model_picker:
            self._on_open_model_picker()

    def _open_agent_mode(self):
        if self._on_open_agent_mode:
            self._on_open_agent_mode()

    def _open_sleep_timer(self):
        if self._on_open_sleep_timer:
            self._on_open_sleep_timer()

    def _open_about(self):
        if self._on_open_about:
            self._on_open_about()

    def _open_companion_app(self):
        if self._on_open_companion_app:
            self._on_open_companion_app()
            return
        ble_addr = self._get_ble_address()
        if not self._on_push_overlay:
            return
        qr = QROverlay(
            url=build_pair_url(ble_addr),
            title="PAIR COMPANION APP",
            subtitle="SCAN WITH YOUR PHONE",
            on_dismiss=lambda: self._on_dismiss_overlay(qr) if self._on_dismiss_overlay else None,
        )
        self._on_push_overlay(qr)
        self._on_set_discoverable(True, 120)

    def _go_back(self):
        if self._on_back:
            self._on_back()


class ModelPickerPanel(BaseScreen):
    OPTIONS = [
        ("SONNET 4.6", "claude-sonnet-4-6"),
        ("OPUS 4.6", "claude-opus-4-6"),
        ("HAIKU 4.5", "claude-haiku-4-5-20251001"),
    ]

    def __init__(self, repository: DeviceRepository, on_back=None, ui_settings: dict | None = None):
        self._repo = repository
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)

        current = str(self._repo.get_setting("ai_model", default="claude-sonnet-4-6"))
        start = 0
        for i, (_, value) in enumerate(self.OPTIONS):
            if value == current:
                start = i
                break
        self._index = start

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._index = (self._index + 1) % len(self.OPTIONS)
        elif action == "LONG_PRESS":
            self._repo.set_setting("ai_model", self.OPTIONS[self._index][1])
            if self._on_back:
                self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.handle_action("LONG_PRESS")

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)
        title = self._font_title.render("MODEL", False, WHITE)
        surface.blit(title, (8, 8))
        pygame.draw.line(surface, HAIRLINE, (0, 24), (PHYSICAL_W, 24))

        current = str(self._repo.get_setting("ai_model", default="claude-sonnet-4-6"))
        y = 44
        for i, (label, value) in enumerate(self.OPTIONS):
            active = "ACTIVE" if value == current else ""
            prefix = ">" if i == self._index else " "
            row = self._font_body.render(f"{prefix}{label}", False, WHITE)
            st = self._font_small.render(active, False, DIM2)
            surface.blit(row, (8, y))
            surface.blit(st, (PHYSICAL_W - st.get_width() - 8, y + 2))
            y += 20

        hint = self._font_small.render("SHORT NEXT • LONG SET", False, DIM3)
        surface.blit(hint, (8, PHYSICAL_H - 14))


class AgentModePanel(BaseScreen):
    OPTIONS = ["producer", "clown", "monk", "hacker", "storyteller", "director"]

    def __init__(self, repository: DeviceRepository, on_back=None, ui_settings: dict | None = None):
        self._repo = repository
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)

        current = str(self._repo.get_setting("agent_mode", default="producer"))
        self._index = self.OPTIONS.index(current) if current in self.OPTIONS else 0

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._index = (self._index + 1) % len(self.OPTIONS)
        elif action == "LONG_PRESS":
            self._repo.set_setting("agent_mode", self.OPTIONS[self._index])
            if self._on_back:
                self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.handle_action("LONG_PRESS")

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)
        title = self._font_title.render("AGENT MODE", False, WHITE)
        surface.blit(title, (8, 8))
        pygame.draw.line(surface, HAIRLINE, (0, 24), (PHYSICAL_W, 24))

        current = str(self._repo.get_setting("agent_mode", default="producer"))
        y = 44
        for i, value in enumerate(self.OPTIONS):
            active = "ACTIVE" if value == current else ""
            prefix = ">" if i == self._index else " "
            row = self._font_body.render(f"{prefix}{value[:10].upper()}", False, WHITE)
            st = self._font_small.render(active, False, DIM2)
            surface.blit(row, (8, y))
            surface.blit(st, (PHYSICAL_W - st.get_width() - 8, y + 2))
            y += 20

        hint = self._font_small.render("SHORT NEXT • LONG SET", False, DIM3)
        surface.blit(hint, (8, PHYSICAL_H - 14))


class SleepTimerPanel(BaseScreen):
    """Stub detail view that shows current timeout and allows returning."""

    def __init__(self, repository: DeviceRepository, on_back=None, ui_settings: dict | None = None):
        self._repo = repository
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)

    def handle_action(self, action: str):
        if action in {"SHORT_PRESS", "LONG_PRESS"} and self._on_back:
            self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
            if self._on_back:
                self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)
        title = self._font_title.render("SLEEP", False, WHITE)
        surface.blit(title, (8, 8))
        pygame.draw.line(surface, HAIRLINE, (0, 24), (PHYSICAL_W, 24))

        timeout = int(self._repo.get_setting("sleep_timeout_seconds", default=60))
        value = self._font_body.render(f"{timeout}s", False, WHITE)
        surface.blit(value, (8, 48))
        hint = self._font_small.render("LONG OR SHORT: BACK", False, DIM3)
        surface.blit(hint, (8, PHYSICAL_H - 14))


class AboutPanel(BaseScreen):
    def __init__(self, on_back=None, ui_settings: dict | None = None):
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)

    def handle_action(self, action: str):
        if action in {"SHORT_PRESS", "LONG_PRESS"} and self._on_back:
            self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
            if self._on_back:
                self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)
        title = self._font_title.render("ABOUT", False, WHITE)
        surface.blit(title, (8, 8))
        pygame.draw.line(surface, HAIRLINE, (0, 24), (PHYSICAL_W, 24))

        lines = [
            "BITOS v1.0",
            "Pi Zero 2W +",
            "Whisplay HAT",
            "Claude Sonnet 4.6",
            "Press Start 2P",
        ]
        y = 44
        for line in lines:
            text = self._font_body.render(line, False, WHITE)
            surface.blit(text, (8, y))
            y += 18


def _compact_model_label(model: str) -> str:
    if model == "claude-opus-4-6":
        return "OPUS"
    if model == "claude-haiku-4-5-20251001":
        return "HAIKU"
    return "SONNET"
