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
from display.tokens import BLACK, DIM2, DIM3, HAIRLINE, PHYSICAL_H, PHYSICAL_W, WHITE, STATUS_BAR_H, ROW_H_MIN
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
        client=None,
        on_open_integration_detail=None,
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

        self._client = client
        self._on_open_integration_detail = on_open_integration_detail
        self._integration_status = {}
        self._blink_phase = False


        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        self._web_search = bool(self._repo.get_setting("web_search", default=True))
        self._memory = bool(self._repo.get_setting("memory", default=True))
        self._ai_model = "claude-sonnet-4-6"
        self._agent_mode = "producer"
        self._sleep_sec = 60

        self._nav = VerticalNavController(
            [
                NavItem(key="web_search", label="WEB SEARCH", status="", action=self._toggle_web_search),
                NavItem(key="memory", label="MEMORY", status="", action=self._toggle_memory),
                NavItem(key="ai_model", label="AI MODEL", status="", action=self._open_model_picker),
                NavItem(key="integrations_header", label="INTEGRATIONS", status="", enabled=False),
                NavItem(key="imessage", label="iMESSAGE", status="", action=lambda: None),
                NavItem(key="vikunja", label="VIKUNJA", status="", action=lambda: None),
                NavItem(key="companion", label="COMPANION APP", status="", action=self._open_companion_app),
                NavItem(key="ai", label="AI", status="", action=self._open_model_picker),
                NavItem(key="bluebubbles", label="BLUEBUBBLES", status="", action=lambda: None),
                NavItem(key="agent_mode", label="AGENT MODE", status="", action=self._open_agent_mode),
                NavItem(key="sleep", label="SLEEP TIMER", status="", action=self._open_sleep_timer),
                NavItem(key="about", label="ABOUT", status="", action=self._open_about),
                NavItem(key="back", label="BACK", status="HOME", action=self._go_back),
            ]
        )

    def on_enter(self):
        self._web_search = bool(self._repo.get_setting("web_search", default=True))
        self._memory = bool(self._repo.get_setting("memory", default=True))
        self._ai_model = str(self._repo.get_setting("ai_model", default="claude-sonnet-4-6"))
        self._agent_mode = str(self._repo.get_setting("agent_mode", default="producer"))
        self._sleep_sec = int(self._repo.get_setting("sleep_timeout_seconds", default=60))
        self._refresh_integration_status()

    def handle_action(self, action: str):
        if action == "LONG_PRESS":
            focused = self._nav.focused_item
            if focused and focused.key in {"imessage", "vikunja"}:
                self._open_integration_detail(focused.key)
            else:
                self._nav.activate_focused()
        elif action == "SHORT_PRESS":
            self._nav.move(1)
        elif action == "DOUBLE_PRESS":
            self._go_back()
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

        # ── Status bar: 18px, inverted (white bg, black text) ──
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("SETTINGS", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        self._blink_phase = not self._blink_phase

        statuses = {
            "web_search": "ON" if self._web_search else "OFF",
            "memory": "ON" if self._memory else "OFF",
            "ai_model": _compact_model_label(self._ai_model) + " \u203a",
            "agent_mode": self._agent_mode[:10].upper() + " \u203a",
            "sleep": f"{self._sleep_sec}s \u203a",
            "about": "v1.0 \u203a",
            "companion": "PAIR \u203a",
            "imessage": self._format_integration_status("imessage", arrow=True),
            "vikunja": self._format_integration_status("vikunja", arrow=True),
            "ai": self._format_integration_status("ai", arrow=True),
            "bluebubbles": self._format_integration_status("imessage", config=True, arrow=True),
            "back": "HOME",
        }

        # ── Rows: 26px minimum, inverted focus ──
        y = STATUS_BAR_H
        for idx, item in enumerate(self._nav.items):
            focused = idx == self._nav.focus_index
            if item.key == "integrations_header":
                row = self._font_body.render(item.label, False, DIM2)
                surface.blit(row, (8, y + (ROW_H_MIN - row.get_height()) // 2))
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
                y += ROW_H_MIN
                continue

            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            status_copy = statuses.get(item.key, item.status)
            row_color = BLACK if focused else WHITE
            status_color = BLACK if focused else DIM2
            row = self._font_body.render(item.label, False, row_color)
            status = self._font_small.render(status_copy, False, status_color)
            text_y = y + (ROW_H_MIN - row.get_height()) // 2
            surface.blit(row, (8, text_y))
            surface.blit(status, (PHYSICAL_W - status.get_width() - 8, text_y + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # ── Key hint bar: 4px font, spec format ──
        hint = self._font_hint.render("SHORT:NEXT \u00b7 LONG:OPEN/TOGGLE \u00b7 DBL:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    def _toggle_web_search(self):
        # VERIFIED: setting toggles persist after back+reopen via repository set/get.
        self._web_search = not self._web_search
        self._repo.set_setting("web_search", self._web_search)
        self.on_enter()

    def _toggle_memory(self):
        # VERIFIED: memory toggle persists and status row reflects saved value on re-enter.
        self._memory = not self._memory
        self._repo.set_setting("memory", self._memory)
        self.on_enter()

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


    def _refresh_integration_status(self):
        if not self._client:
            self._integration_status = {}
            return
        try:
            self._integration_status = self._client.get_integration_status()
        except Exception:
            self._integration_status = {}

    def _format_integration_status(self, key: str, config: bool = False, arrow: bool = False) -> str:
        info = self._integration_status.get(key, {})
        status = str(info.get("status", "offline")).lower()
        if config:
            status = "config"
        if status == "online":
            label = "[ONLINE]"
        elif status == "offline":
            label = "[OFFLINE]"
        elif status == "config":
            label = "[CONFIG]" if self._blink_phase else "[      ]"
        elif status == "mock":
            label = "MOCK"
        else:
            label = "[OFFLINE]"
        return f"{label} ›" if arrow else label

    def _open_integration_detail(self, integration_name: str):
        if self._on_open_integration_detail:
            status_data = self._integration_status.get(integration_name, {})
            self._on_open_integration_detail(integration_name, status_data)

    def _go_back(self):
        if self._on_back:
            self._on_back()


class ModelPickerPanel(BaseScreen):
    OPTIONS = [
        ("SONNET 4.6", "claude-sonnet-4-6"),
        ("OPUS 4.6", "claude-opus-4-6"),
        ("HAIKU 4.5", "claude-haiku-4-5-20251001"),
    ]

    MODEL_SUBTITLES = {
        "claude-sonnet-4-6": "FAST \u00b7 BALANCED \u00b7 DEFAULT",
        "claude-opus-4-6": "POWERFUL \u00b7 SLOWER",
        "claude-haiku-4-5-20251001": "FASTEST \u00b7 LIGHTWEIGHT",
    }

    def __init__(self, repository: DeviceRepository, on_back=None, ui_settings: dict | None = None):
        self._repo = repository
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        current = str(self._repo.get_setting("ai_model", default="claude-sonnet-4-6"))
        start = 0
        for i, (_, value) in enumerate(self.OPTIONS):
            if value == current:
                start = i
                break
        self._index = start
        self._current_model = current

    def on_enter(self):
        self._current_model = str(self._repo.get_setting("ai_model", default="claude-sonnet-4-6"))
        for i, (_, value) in enumerate(self.OPTIONS):
            if value == self._current_model:
                self._index = i
                break

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._index = (self._index + 1) % len(self.OPTIONS)
        elif action == "LONG_PRESS":
            self._repo.set_setting("ai_model", self.OPTIONS[self._index][1])
            self.on_enter()
            if self._on_back:
                self._on_back()
        elif action == "DOUBLE_PRESS":
            if self._on_back:
                self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.handle_action("LONG_PRESS")
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self._on_back:
                self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # ── Status bar: inverted ──
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("AI MODEL", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        # ── Rows: 26px, inverted focus ──
        y = STATUS_BAR_H + 2
        for i, (label, value) in enumerate(self.OPTIONS):
            focused = i == self._index
            is_active = value == self._current_model
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            row_color = BLACK if focused else (WHITE if is_active else DIM2)
            row = self._font_body.render(label, False, row_color)
            text_y = y + 4
            surface.blit(row, (8, text_y))
            badge = "ACTIVE" if is_active else ""
            if badge:
                badge_color = BLACK if focused else DIM2
                st = self._font_small.render(badge, False, badge_color)
                surface.blit(st, (PHYSICAL_W - st.get_width() - 8, text_y + 2))
            subtitle = self.MODEL_SUBTITLES.get(value, "")
            if subtitle:
                sub_color = BLACK if focused else DIM3
                sub_surface = self._font_small.render(subtitle, False, sub_color)
                surface.blit(sub_surface, (8, text_y + row.get_height() + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # ── Key hint bar ──
        hint = self._font_hint.render("SHORT:NEXT \u00b7 LONG:SELECT \u00b7 DBL:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))


class AgentModePanel(BaseScreen):
    OPTIONS = ["producer", "clown", "monk", "hacker", "storyteller", "director"]
    SUBTITLES = {
        "producer": "Operations \u00b7 coordination",
        "clown": "Performance \u00b7 improv",
        "monk": "Focus \u00b7 reflection",
        "hacker": "Code \u00b7 systems",
        "storyteller": "Narrative \u00b7 creative",
        "director": "Strategy \u00b7 vision",
    }

    def __init__(self, repository: DeviceRepository, on_back=None, ui_settings: dict | None = None):
        self._repo = repository
        self._on_back = on_back

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        current = str(self._repo.get_setting("agent_mode", default="producer"))
        self._index = self.OPTIONS.index(current) if current in self.OPTIONS else 0
        self._current_mode = current

    def on_enter(self):
        self._current_mode = str(self._repo.get_setting("agent_mode", default="producer"))
        self._index = self.OPTIONS.index(self._current_mode) if self._current_mode in self.OPTIONS else 0

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._index = (self._index + 1) % len(self.OPTIONS)
        elif action == "LONG_PRESS":
            self._repo.set_setting("agent_mode", self.OPTIONS[self._index])
            self.on_enter()
            if self._on_back:
                self._on_back()
        elif action == "DOUBLE_PRESS":
            if self._on_back:
                self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.handle_action("LONG_PRESS")
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self._on_back:
                self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # ── Status bar: inverted ──
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("AGENT MODE", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        # ── Rows: 26px, inverted focus ──
        y = STATUS_BAR_H + 2
        for i, value in enumerate(self.OPTIONS):
            focused = i == self._index
            is_active = value == self._current_mode
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            row_color = BLACK if focused else (WHITE if is_active else DIM2)
            row = self._font_body.render(value[:10].upper(), False, row_color)
            text_y = y + 4
            surface.blit(row, (8, text_y))
            badge = "ACTIVE" if is_active else ""
            if badge:
                badge_color = BLACK if focused else DIM2
                st = self._font_small.render(badge, False, badge_color)
                surface.blit(st, (PHYSICAL_W - st.get_width() - 8, text_y + 2))
            subtitle = self.SUBTITLES.get(value, "")
            if subtitle:
                sub_color = BLACK if focused else DIM3
                sub_surface = self._font_small.render(subtitle, False, sub_color)
                surface.blit(sub_surface, (8, text_y + row.get_height() + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # ── Key hint bar ──
        hint = self._font_hint.render("SHORT:NEXT \u00b7 LONG:SELECT \u00b7 DBL:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))


class SleepTimerPanel(BaseScreen):
    """Stub detail view that shows current timeout and allows returning."""

    def __init__(self, repository: DeviceRepository, on_back=None, ui_settings: dict | None = None):
        self._repo = repository
        self._on_back = on_back

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)
        self._timeout = int(self._repo.get_setting("sleep_timeout_seconds", default=60))

    def on_enter(self):
        self._timeout = int(self._repo.get_setting("sleep_timeout_seconds", default=60))

    def handle_action(self, action: str):
        if action == "DOUBLE_PRESS" and self._on_back:
            self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
            if self._on_back:
                self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # ── Status bar: inverted ──
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("SLEEP TIMER", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        value = self._font_title.render(f"{self._timeout}s", False, WHITE)
        surface.blit(value, ((PHYSICAL_W - value.get_width()) // 2, 48))

        # ── Key hint bar ──
        hint = self._font_hint.render("DBL:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))


class AboutPanel(BaseScreen):
    def __init__(self, on_back=None, ui_settings: dict | None = None):
        self._on_back = on_back

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

    def handle_action(self, action: str):
        if action == "DOUBLE_PRESS" and self._on_back:
            self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
            if self._on_back:
                self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # ── Status bar: inverted ──
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("ABOUT", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        lines = [
            "BITOS v1.0",
            "Pi Zero 2W +",
            "Whisplay HAT",
            "Claude Sonnet 4.6",
            "Press Start 2P",
        ]
        y = STATUS_BAR_H + 8
        for line in lines:
            text = self._font_body.render(line, False, WHITE)
            surface.blit(text, (8, y))
            y += ROW_H_MIN

        # ── Key hint bar ──
        hint = self._font_hint.render("DBL:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))


def _compact_model_label(model: str) -> str:
    if model == "claude-opus-4-6":
        return "OPUS"
    if model == "claude-haiku-4-5-20251001":
        return "HAIKU"
    return "SONNET"
