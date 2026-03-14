"""BITOS Home panel with button-first sidebar navigation."""
import threading

import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM2, DIM3, HAIRLINE, PHYSICAL_W, PHYSICAL_H, STATUS_BAR_H, ROW_H_MIN
from display.theme import merge_runtime_ui_settings, load_ui_font
from screens.components import NavItem, VerticalNavController


class HomePanel(BaseScreen):
    """Home panel with focusable sidebar entries and action routing."""

    def __init__(
        self,
        on_open_chat=None,
        on_open_focus=None,
        on_open_tasks=None,
        on_open_captures=None,
        on_open_notifications=None,
        on_open_messages=None,
        on_open_settings=None,
        on_show_shade=None,
        ui_settings: dict | None = None,
        startup_health: dict | None = None,
        repository=None,
        client=None,
    ):
        self._on_open_chat = on_open_chat
        self._on_open_focus = on_open_focus
        self._on_open_tasks = on_open_tasks
        self._on_open_captures = on_open_captures
        self._on_open_notifications = on_open_notifications
        self._on_open_messages = on_open_messages
        self._on_open_settings = on_open_settings
        self._on_show_shade = on_show_shade
        self._repository = repository
        self._client = None
        self._msgs_unread = 0
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._client = client
        self._startup_health = startup_health if startup_health is not None else {}
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)
        self._nav = VerticalNavController(
            [
                NavItem(key="chat", label="CHAT", status="READY", action=self._open_chat),
                NavItem(key="focus", label="FOCUS", status="READY", action=self._open_focus),
                NavItem(key="notifs", label="NOTIFS", status="READY", action=self._open_notifications),
                NavItem(key="settings", label="SETTINGS", status="READY", action=self._open_settings),
                NavItem(key="tasks", label="TASKS", status="SYNC", action=self._open_tasks),
                NavItem(key="msgs", label="MSGS", status="SYNC", action=self._open_messages),
                NavItem(key="captures", label="CAPTURES", status="", action=self._open_captures),
            ]
        )

        if self._client:
            threading.Thread(target=self._refresh_unread, daemon=True).start()

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._nav.activate_focused()
        elif action == "DOUBLE_PRESS":
            self._open_shade()
        elif action == "LONG_PRESS":
            focused = self._nav.focused_item
            if focused and focused.key == "msgs":
                self._open_messages()
            else:
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

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("HOME", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))
        health = self._health_indicator()
        health_surface = self._font_small.render(health, False, BLACK)
        surface.blit(health_surface, (PHYSICAL_W - health_surface.get_width() - 6, (STATUS_BAR_H - health_surface.get_height()) // 2))

        y = STATUS_BAR_H + 2
        capture_count = self._repository.get_capture_count() if self._repository else 0
        for idx, item in enumerate(self._nav.items):
            focused = idx == self._nav.focus_index
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            row_color = BLACK if focused else (WHITE if item.enabled else DIM3)
            status_color = BLACK if focused else (DIM2 if item.enabled else DIM3)
            label = item.label
            if item.key == "captures":
                label = f"CAPTURES ({capture_count})"
            elif item.key == "msgs":
                label = f"MSGS ({self._msgs_unread})" if self._msgs_unread > 0 else "MSGS"
            row = self._font_body.render(label, False, row_color)
            st = self._font_small.render(item.status, False, status_color)
            text_y = y + (ROW_H_MIN - row.get_height()) // 2
            surface.blit(row, (8, text_y))
            surface.blit(st, (PHYSICAL_W - st.get_width() - 8, text_y + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        hint = self._font_hint.render("SHORT:SEL · LONG:NEXT · DBL:SHADE", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    def _open_chat(self):
        # VERIFIED: HOME CHAT nav opens ChatPanel.
        if self._on_open_chat:
            self._on_open_chat()

    def _open_focus(self):
        # VERIFIED: HOME FOCUS nav opens FocusPanel.
        if self._on_open_focus:
            self._on_open_focus()

    def _open_tasks(self):
        # VERIFIED: HOME TASKS nav opens TasksPanel.
        if self._on_open_tasks:
            self._on_open_tasks()

    def _open_captures(self):
        # VERIFIED: HOME CAPTURES nav opens CapturesPanel.
        if self._on_open_captures:
            self._on_open_captures()

    def _open_messages(self):
        if self._on_open_messages:
            self._on_open_messages()

    def _open_notifications(self):
        # VERIFIED: HOME NOTIFS nav opens NotificationsPanel.
        if self._on_open_notifications:
            self._on_open_notifications()

    def _open_settings(self):
        # VERIFIED: HOME SETTINGS nav opens SettingsPanel.
        if self._on_open_settings:
            self._on_open_settings()

    def _open_shade(self):
        if self._on_show_shade:
            self._on_show_shade()

    def _health_indicator(self) -> str:
        backend = self._startup_health.get("backend")
        if backend is None:
            return "AI ?"
        return "AI ✓" if backend else "AI ⚠"

    def _refresh_unread(self):
        try:
            conversations = self._client.get_conversations() if self._client else []
            self._msgs_unread = sum(int(c.get("unread", 0)) for c in conversations)
        except Exception:
            self._msgs_unread = 0
