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
    _owns_status_bar = True

    def __init__(
        self,
        repository: DeviceRepository,
        on_back=None,
        on_open_model_picker=None,
        on_open_agent_mode=None,
        on_open_sleep_timer=None,
        on_open_about=None,
        on_open_companion_app=None,
        on_open_change_pin=None,
        on_open_battery=None,
        on_open_dev=None,
        on_open_font_picker=None,
        on_open_text_speed=None,
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
        self._on_open_change_pin = on_open_change_pin
        self._on_open_battery = on_open_battery
        self._on_open_dev = on_open_dev
        self._on_open_font_picker = on_open_font_picker
        self._on_open_text_speed = on_open_text_speed
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
        self._firmware_status = "v1.0"  # Updated on enter
        self._update_available = False

        self._nav = VerticalNavController([
            NavItem(key="web_search", label="WEB SEARCH", status="", action=self._toggle_web_search),
            NavItem(key="memory", label="MEMORY", status="", action=self._toggle_memory),
            NavItem(key="ai_model", label="AI MODEL", status="", action=self._open_model_picker),
            NavItem(key="agent_mode", label="AGENT MODE", status="", action=self._open_agent_mode),
            NavItem(key="sleep", label="SLEEP TIMER", status="", action=self._open_sleep_timer),
            NavItem(key="font", label="FONT", status="", action=self._open_font_picker),
            NavItem(key="text_speed", label="TEXT SPEED", status="", action=self._open_text_speed),
            NavItem(key="firmware", label="FIRMWARE", status="", action=self._check_firmware),
            NavItem(key="about", label="ABOUT", status="", action=self._open_about),
            NavItem(key="battery", label="BATTERY", status="", action=self._open_battery),
            NavItem(key="companion", label="COMPANION APP", status="", action=self._open_companion_app),
            NavItem(key="change_pin", label="CHANGE PIN", status="", action=self._open_change_pin),
            NavItem(key="dev", label="DEV MODE", status="", action=self._open_dev),
            NavItem(key="integrations_header", label="─ INTEGRATIONS ─", status="", enabled=False),
            NavItem(key="imessage", label="iMESSAGE", status="", action=lambda: self._open_integration_detail("imessage")),
            NavItem(key="vikunja", label="VIKUNJA", status="", action=lambda: self._open_integration_detail("vikunja")),
            NavItem(key="back", label="BACK", status="HOME", action=self._go_back),
        ])

    def on_enter(self):
        self._web_search = bool(self._repo.get_setting("web_search", default=True))
        self._memory = bool(self._repo.get_setting("memory", default=True))
        self._ai_model = str(self._repo.get_setting("ai_model", default="claude-sonnet-4-6"))
        self._agent_mode = str(self._repo.get_setting("agent_mode", default="producer"))
        self._sleep_sec = int(self._repo.get_setting("sleep_timeout_seconds", default=60))
        self._font_family = str(self._repo.get_setting("font_family", default="press_start_2p"))
        self._refresh_integration_status()
        self._refresh_firmware_status()

    def handle_action(self, action: str):
        if action == "DOUBLE_PRESS":
            focused = self._nav.focused_item
            if focused and focused.key in {"imessage", "vikunja"}:
                self._open_integration_detail(focused.key)
            else:
                self._nav.activate_focused()
        elif action == "SHORT_PRESS":
            self._nav.move(1)
        elif action == "LONG_PRESS":
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
            "font": self._font_family_label() + " \u203a",
            "firmware": self._firmware_status,
            "about": "v1.0 \u203a",
            "companion": "PAIR \u203a",
            "battery": "\u203a",
            "change_pin": "\u203a",
            "dev": "\u203a",
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
            indicator = "> " if focused else "- "
            row = self._font_body.render(indicator + item.label, False, row_color)
            status = self._font_small.render(status_copy, False, status_color)
            text_y = y + (ROW_H_MIN - row.get_height()) // 2
            surface.blit(row, (4, text_y))
            surface.blit(status, (PHYSICAL_W - status.get_width() - 8, text_y + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # ── Key hint bar: 4px font, spec format ──
        hint = self._font_hint.render("SHORT:NEXT \u00b7 DBL:OPEN/TOGGLE \u00b7 LONG:BACK", False, DIM3)
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

    def _open_font_picker(self):
        if self._on_open_font_picker:
            self._on_open_font_picker()

    def _open_text_speed(self):
        if self._on_open_text_speed:
            self._on_open_text_speed()

    def _font_family_label(self) -> str:
        if self._font_family == "monocraft":
            return "MONO"
        return "PS2P"

    def _open_about(self):
        if self._on_open_about:
            self._on_open_about()

    def _open_change_pin(self):
        if self._on_open_change_pin:
            self._on_open_change_pin()

    def _open_battery(self):
        if self._on_open_battery:
            self._on_open_battery()

    def _open_dev(self):
        if self._on_open_dev:
            self._on_open_dev()

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


    def _refresh_firmware_status(self):
        """Check server for firmware version info."""
        if not self._client:
            return
        try:
            info = self._client.get_device_version()
            commit = info.get("commit", "?")[:7]
            self._update_available = bool(info.get("update_available"))
            if self._update_available:
                behind = info.get("behind", 0)
                self._firmware_status = f"{commit} UPDATE \u203a"
            else:
                self._firmware_status = f"{commit} \u2713"
        except Exception:
            self._firmware_status = "v1.0 \u203a"

    def _check_firmware(self):
        """Check for updates and trigger if available."""
        if not self._client:
            return
        if self._update_available:
            # Trigger the update
            self._firmware_status = "UPDATING..."
            try:
                self._client.trigger_update()
            except Exception:
                self._firmware_status = "UPDATE FAILED"
        else:
            # Just refresh the status
            self._refresh_firmware_status()

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
    _owns_status_bar = True
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
        elif action == "DOUBLE_PRESS":
            self._repo.set_setting("ai_model", self.OPTIONS[self._index][1])
            self.on_enter()
            if self._on_back:
                self._on_back()
        elif action == "LONG_PRESS":
            if self._on_back:
                self._on_back()
        elif action == "TRIPLE_PRESS":
            self._index = (self._index - 1) % len(self.OPTIONS)

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.handle_action("DOUBLE_PRESS")
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
            indicator = "> " if focused else "- "
            row = self._font_body.render(indicator + label, False, row_color)
            text_y = y + 4
            surface.blit(row, (4, text_y))
            badge = "ACTIVE" if is_active else ""
            if badge:
                badge_color = BLACK if focused else DIM2
                st = self._font_small.render(badge, False, badge_color)
                surface.blit(st, (PHYSICAL_W - st.get_width() - 8, text_y + 2))
            subtitle = self.MODEL_SUBTITLES.get(value, "")
            if subtitle:
                sub_color = BLACK if focused else DIM3
                sub_surface = self._font_small.render(subtitle, False, sub_color)
                surface.blit(sub_surface, (4, text_y + row.get_height() + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # ── Key hint bar ──
        hint = self._font_hint.render("SHORT:NEXT \u00b7 DBL:SELECT \u00b7 LONG:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))


class AgentModePanel(BaseScreen):
    _owns_status_bar = True
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
        elif action == "DOUBLE_PRESS":
            self._repo.set_setting("agent_mode", self.OPTIONS[self._index])
            self.on_enter()
            if self._on_back:
                self._on_back()
        elif action == "LONG_PRESS":
            if self._on_back:
                self._on_back()
        elif action == "TRIPLE_PRESS":
            self._index = (self._index - 1) % len(self.OPTIONS)

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.handle_action("DOUBLE_PRESS")
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
            indicator = "> " if focused else "- "
            row = self._font_body.render(indicator + value[:10].upper(), False, row_color)
            text_y = y + 4
            surface.blit(row, (4, text_y))
            badge = "ACTIVE" if is_active else ""
            if badge:
                badge_color = BLACK if focused else DIM2
                st = self._font_small.render(badge, False, badge_color)
                surface.blit(st, (PHYSICAL_W - st.get_width() - 8, text_y + 2))
            subtitle = self.SUBTITLES.get(value, "")
            if subtitle:
                sub_color = BLACK if focused else DIM3
                sub_surface = self._font_small.render(subtitle, False, sub_color)
                surface.blit(sub_surface, (4, text_y + row.get_height() + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # ── Key hint bar ──
        hint = self._font_hint.render("SHORT:NEXT \u00b7 DBL:SELECT \u00b7 LONG:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))


class SleepTimerPanel(BaseScreen):
    """Sleep timer picker — cycle through timeout values, save on DOUBLE_PRESS."""
    _owns_status_bar = True

    OPTIONS = [
        (30, "30 SEC"),
        (60, "1 MIN"),
        (120, "2 MIN"),
        (300, "5 MIN"),
        (600, "10 MIN"),
        (0, "NEVER"),
    ]

    def __init__(self, repository: DeviceRepository, on_back=None, ui_settings: dict | None = None):
        self._repo = repository
        self._on_back = on_back

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)
        self._timeout = int(self._repo.get_setting("sleep_timeout_seconds", default=60) or 60)
        self._index = self._find_index(self._timeout)

    def _find_index(self, timeout: int) -> int:
        for i, (val, _) in enumerate(self.OPTIONS):
            if val == timeout:
                return i
        return 1  # default to 60s

    def on_enter(self):
        self._timeout = int(self._repo.get_setting("sleep_timeout_seconds", default=60) or 60)
        self._index = self._find_index(self._timeout)

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._index = (self._index + 1) % len(self.OPTIONS)
        elif action == "TRIPLE_PRESS":
            self._index = (self._index - 1) % len(self.OPTIONS)
        elif action == "DOUBLE_PRESS":
            self._repo.set_setting("sleep_timeout_seconds", self.OPTIONS[self._index][0])
            if self._on_back:
                self._on_back()
        elif action == "LONG_PRESS":
            if self._on_back:
                self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.handle_action("DOUBLE_PRESS")
            elif event.key == pygame.K_ESCAPE:
                if self._on_back:
                    self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # ── Status bar: inverted ──
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("SLEEP TIMER", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        # ── Options list ──
        y = STATUS_BAR_H + 2
        for i, (val, label) in enumerate(self.OPTIONS):
            focused = i == self._index
            is_active = val == self._timeout
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            row_color = BLACK if focused else (WHITE if is_active else DIM2)
            indicator = "> " if focused else "- "
            row = self._font_body.render(indicator + label, False, row_color)
            text_y = y + (ROW_H_MIN - row.get_height()) // 2
            surface.blit(row, (4, text_y))
            if is_active:
                badge_color = BLACK if focused else DIM2
                badge = self._font_small.render("ACTIVE", False, badge_color)
                surface.blit(badge, (PHYSICAL_W - badge.get_width() - 8, text_y + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # ── Key hint bar ──
        hint = self._font_hint.render("SHORT:NEXT \u00b7 DBL:SELECT \u00b7 LONG:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))


class AboutPanel(BaseScreen):
    _owns_status_bar = True
    def __init__(self, on_back=None, ui_settings: dict | None = None):
        self._on_back = on_back

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

    def handle_action(self, action: str):
        if action == "LONG_PRESS" and self._on_back:
            self._on_back()
        elif action in {"SHORT_PRESS", "DOUBLE_PRESS", "TRIPLE_PRESS"}:
            return

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
        hint = self._font_hint.render("LONG:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))


class BatteryPanel(BaseScreen):
    """Battery status and safe-shutdown configuration."""
    _owns_status_bar = True

    SHUTDOWN_OPTIONS = [3, 5, 10, 15, 20]

    def __init__(self, battery_monitor, repository: DeviceRepository, on_back=None, ui_settings: dict | None = None):
        self._battery = battery_monitor
        self._repo = repository
        self._on_back = on_back

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        self._shutdown_threshold = int(self._repo.get_setting("safe_shutdown_pct", 5) or 5)
        self._editing_threshold = False
        self._threshold_index = self._find_threshold_index()

    def _find_threshold_index(self) -> int:
        for i, val in enumerate(self.SHUTDOWN_OPTIONS):
            if val == self._shutdown_threshold:
                return i
        return 1  # default to 5%

    def on_enter(self):
        self._shutdown_threshold = int(self._repo.get_setting("safe_shutdown_pct", 5) or 5)
        self._threshold_index = self._find_threshold_index()

    def handle_action(self, action: str):
        if self._editing_threshold:
            if action == "SHORT_PRESS":
                self._threshold_index = (self._threshold_index + 1) % len(self.SHUTDOWN_OPTIONS)
            elif action == "TRIPLE_PRESS":
                self._threshold_index = (self._threshold_index - 1) % len(self.SHUTDOWN_OPTIONS)
            elif action == "DOUBLE_PRESS":
                new_val = self.SHUTDOWN_OPTIONS[self._threshold_index]
                self._repo.set_setting("safe_shutdown_pct", new_val)
                self._shutdown_threshold = new_val
                self._battery.configure_safe_shutdown(threshold_pct=new_val, delay_s=30)
                self._editing_threshold = False
            elif action == "LONG_PRESS":
                self._editing_threshold = False
            return

        if action == "DOUBLE_PRESS":
            self._editing_threshold = True
        elif action == "LONG_PRESS":
            if self._on_back:
                self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self._on_back:
                self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # Status bar
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("BATTERY", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        status = self._battery.get_status()
        pct = status.get("pct", 0)
        charging = status.get("charging", False)
        plugged = status.get("plugged", False)
        model = status.get("model", "unknown")

        y = STATUS_BAR_H + 8

        # Big percentage
        pct_text = f"{pct}%"
        pct_surf = self._font_title.render(pct_text, False, WHITE)
        surface.blit(pct_surf, ((PHYSICAL_W - pct_surf.get_width()) // 2, y))
        y += pct_surf.get_height() + 2

        # Charging status
        if charging:
            charge_text = "CHARGING"
        elif plugged:
            charge_text = "PLUGGED IN"
        else:
            charge_text = "ON BATTERY"
        charge_surf = self._font_small.render(charge_text, False, DIM2)
        surface.blit(charge_surf, ((PHYSICAL_W - charge_surf.get_width()) // 2, y))
        y += charge_surf.get_height() + 12

        # Battery bar
        bar_x, bar_w, bar_h = 16, PHYSICAL_W - 32, 12
        pygame.draw.rect(surface, DIM3, (bar_x, y, bar_w, bar_h), 1)
        fill_w = max(1, int((bar_w - 2) * pct / 100))
        bar_color = WHITE if pct > 20 else (0xFF, 0x44, 0x44)
        pygame.draw.rect(surface, bar_color, (bar_x + 1, y + 1, fill_w, bar_h - 2))
        y += bar_h + 12

        # Info rows
        rows = [
            ("MODEL", model.upper()),
            ("SAFE SHUTDOWN", f"{self._shutdown_threshold}%"),
        ]
        for label, value in rows:
            editing = self._editing_threshold and label == "SAFE SHUTDOWN"
            if editing:
                value = f"[{self.SHUTDOWN_OPTIONS[self._threshold_index]}%]"
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            label_color = BLACK if editing else DIM2
            value_color = BLACK if editing else WHITE
            label_surf = self._font_small.render(label, False, label_color)
            value_surf = self._font_body.render(value, False, value_color)
            text_y = y + (ROW_H_MIN - label_surf.get_height()) // 2
            surface.blit(label_surf, (8, text_y))
            surface.blit(value_surf, (PHYSICAL_W - value_surf.get_width() - 8, text_y))
            if not editing:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # Hint
        if self._editing_threshold:
            hint_text = "SHORT:NEXT \u00b7 DBL:SAVE \u00b7 LONG:CANCEL"
        else:
            hint_text = "DBL:EDIT SHUTDOWN \u00b7 LONG:BACK"
        hint = self._font_hint.render(hint_text, False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))


class DevPanel(BaseScreen):
    """Developer diagnostics: CPU, RAM, temp, disk, uptime, IP, commit."""
    _owns_status_bar = True

    def __init__(self, system_monitor, on_back=None, ui_settings: dict | None = None):
        self._monitor = system_monitor
        self._on_back = on_back

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        self._snapshot: dict = {}
        self._refresh_timer = 0.0
        self._start_time = 0.0

    def on_enter(self):
        import time as _time
        self._start_time = _time.time()
        self._refresh()

    def update(self, dt: float):
        self._refresh_timer += dt
        if self._refresh_timer >= 2.0:
            self._refresh_timer = 0.0
            self._refresh()

    def _refresh(self):
        self._snapshot = self._monitor.get_snapshot()

    def handle_action(self, action: str):
        if action == "LONG_PRESS":
            if self._on_back:
                self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self._on_back:
                self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # Status bar
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("DEV MODE", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        snap = self._snapshot
        cpu = snap.get("cpu_percent", 0)
        ram_used = snap.get("ram_used_mb", 0)
        ram_total = snap.get("ram_total_mb", 0)
        ram_pct = snap.get("ram_percent", 0)
        temp = snap.get("temp_c", 0)
        disk = snap.get("disk_percent", 0)

        # Uptime
        import time as _time
        uptime_s = int(_time.time() - self._start_time) if self._start_time else 0
        uptime_m = uptime_s // 60
        uptime_h = uptime_m // 60
        if uptime_h > 0:
            uptime_str = f"{uptime_h}H {uptime_m % 60}M"
        else:
            uptime_str = f"{uptime_m}M {uptime_s % 60}S"

        # IP address
        ip_str = self._get_ip()

        # Git commit
        commit = self._get_commit()

        rows = [
            ("CPU", f"{cpu:.0f}%"),
            ("RAM", f"{ram_used}/{ram_total}MB ({ram_pct:.0f}%)"),
            ("TEMP", f"{temp}\u00b0C" if temp else "N/A"),
            ("DISK", f"{disk:.0f}%"),
            ("UPTIME", uptime_str),
            ("IP", ip_str),
            ("COMMIT", commit),
        ]

        y = STATUS_BAR_H + 4
        for label, value in rows:
            label_surf = self._font_small.render(label, False, DIM2)
            value_surf = self._font_body.render(value, False, WHITE)
            text_y = y + (ROW_H_MIN - label_surf.get_height()) // 2
            surface.blit(label_surf, (8, text_y))
            surface.blit(value_surf, (PHYSICAL_W - value_surf.get_width() - 8, text_y))
            pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # Hint
        hint = self._font_hint.render("LONG:BACK \u00b7 AUTO-REFRESH 2S", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    @staticmethod
    def _get_ip() -> str:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "NO NETWORK"

    @staticmethod
    def _get_commit() -> str:
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=2, check=False,
            )
            return result.stdout.strip() or "unknown"
        except Exception:
            return "unknown"


class FontPickerPanel(BaseScreen):
    """Font family picker — cycle through available fonts, save on DOUBLE_PRESS."""
    _owns_status_bar = True

    OPTIONS = [
        ("press_start_2p", "PRESS START 2P"),
        ("monocraft", "MONOCRAFT"),
    ]

    def __init__(self, repository: DeviceRepository, on_back=None, ui_settings: dict | None = None):
        self._repo = repository
        self._on_back = on_back

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        self._current_family = str(self._repo.get_setting("font_family", default="press_start_2p"))
        self._index = self._find_index(self._current_family)

    def _find_index(self, family: str) -> int:
        for i, (val, _) in enumerate(self.OPTIONS):
            if val == family:
                return i
        return 0

    def on_enter(self):
        self._current_family = str(self._repo.get_setting("font_family", default="press_start_2p"))
        self._index = self._find_index(self._current_family)

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._index = (self._index + 1) % len(self.OPTIONS)
        elif action == "TRIPLE_PRESS":
            self._index = (self._index - 1) % len(self.OPTIONS)
        elif action == "DOUBLE_PRESS":
            selected_family = self.OPTIONS[self._index][0]
            self._repo.set_setting("font_family", selected_family)
            from display.theme import flush_font_cache
            flush_font_cache()
            if self._on_back:
                self._on_back()
        elif action == "LONG_PRESS":
            if self._on_back:
                self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.handle_action("DOUBLE_PRESS")
            elif event.key == pygame.K_ESCAPE:
                if self._on_back:
                    self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("FONT", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        y = STATUS_BAR_H + 2
        for i, (family, label) in enumerate(self.OPTIONS):
            focused = i == self._index
            is_active = family == self._current_family
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            row_color = BLACK if focused else (WHITE if is_active else DIM2)
            indicator = "> " if focused else "- "
            row = self._font_body.render(indicator + label, False, row_color)
            text_y = y + (ROW_H_MIN - row.get_height()) // 2
            surface.blit(row, (4, text_y))
            if is_active:
                badge_color = BLACK if focused else DIM2
                badge = self._font_small.render("ACTIVE", False, badge_color)
                surface.blit(badge, (PHYSICAL_W - badge.get_width() - 8, text_y + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # Preview using selected font
        y += 8
        selected_family = self.OPTIONS[self._index][0]
        from display.tokens import FONT_REGISTRY
        preview_path = FONT_REGISTRY.get(selected_family)
        try:
            preview_font = pygame.font.Font(preview_path, 12)
        except Exception:
            preview_font = self._font_body
        preview = preview_font.render("HELLO WORLD 123", False, DIM2)
        surface.blit(preview, (8, y))

        hint = self._font_hint.render("SHORT:NEXT \u00b7 DBL:SELECT \u00b7 LONG:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))


class TextSpeedPanel(BaseScreen):
    """Pick typewriter text reveal speed."""
    _owns_status_bar = True

    OPTIONS = [
        ("slow", "SLOW"),
        ("normal", "NORMAL"),
        ("fast", "FAST"),
        ("instant", "INSTANT"),
    ]

    def __init__(self, repository: DeviceRepository, on_back=None, ui_settings=None):
        self._repo = repository
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        current = str(self._repo.get_setting("text_speed", "normal"))
        self._selected = next((i for i, (v, _) in enumerate(self.OPTIONS) if v == current), 1)

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._selected = (self._selected + 1) % len(self.OPTIONS)
        elif action == "TRIPLE_PRESS":
            self._selected = (self._selected - 1) % len(self.OPTIONS)
        elif action == "DOUBLE_PRESS":
            value, _ = self.OPTIONS[self._selected]
            self._repo.set_setting("text_speed", value)
            if self._on_back:
                self._on_back()
        elif action == "LONG_PRESS":
            if self._on_back:
                self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)
        header = self._font_small.render("TEXT SPEED", False, WHITE)
        surface.blit(header, (8, 2))
        y = STATUS_BAR_H + 4
        for i, (value, label) in enumerate(self.OPTIONS):
            focused = i == self._selected
            prefix = "> " if focused else "- "
            color = WHITE if focused else DIM2
            text = self._font.render(prefix + label, False, color)
            surface.blit(text, (8, y))
            y += ROW_H_MIN


def _compact_model_label(model: str) -> str:
    if model == "claude-opus-4-6":
        return "OPUS"
    if model == "claude-haiku-4-5-20251001":
        return "HAIKU"
    return "SONNET"
