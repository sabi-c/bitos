"""BITOS Home panel with button-first sidebar navigation."""

from datetime import datetime

import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM2, DIM3, HAIRLINE, PHYSICAL_W, PHYSICAL_H, STATUS_BAR_H, ROW_H_MIN
from display.theme import merge_runtime_ui_settings, load_ui_font
from screens.components import NavItem, VerticalNavController, Widget, WidgetStrip


class HomePanel(BaseScreen):
    """Home panel with focusable sidebar entries and action routing."""
    _owns_status_bar: bool = True

    def __init__(
        self,
        on_back=None,
        on_open_chat=None,
        on_open_focus=None,
        on_open_tasks=None,
        on_open_captures=None,
        on_open_notifications=None,
        on_open_messages=None,
        on_open_mail=None,
        on_open_settings=None,
        on_show_shade=None,
        ui_settings: dict | None = None,
        startup_health: dict | None = None,
        repository=None,
        client=None,
        status_state=None,
    ):
        self._on_open_chat = on_open_chat
        self._on_back = on_back
        self._on_open_focus = on_open_focus
        self._on_open_tasks = on_open_tasks
        self._on_open_captures = on_open_captures
        self._on_open_notifications = on_open_notifications
        self._on_open_messages = on_open_messages
        self._on_open_mail = on_open_mail
        self._on_open_settings = on_open_settings
        self._on_show_shade = on_show_shade
        self._repository = repository
        self._status_state = status_state
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._client = client
        self._startup_health = startup_health if startup_health is not None else {}
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)
        self._capture_count = 0
        self._capture_refresh_elapsed = 5.0
        self._widget_strip = WidgetStrip([
            Widget(key="time", label="TIME", value=datetime.now().strftime("%H:%M")),
            Widget(key="weather", label="WEATHER", value="--"),
            Widget(key="unread", label="UNREAD", value="0"),
        ])
        self._widget_fonts = {
            "hint": self._font_hint,
            "small": self._font_small,
        }
        self._ticker_text: str = ""
        self._ticker_offset: int = 0
        self._nav = VerticalNavController(
            [
                NavItem(key="chat", label="CHAT", status="READY", action=self._open_chat),
                NavItem(key="focus", label="FOCUS", status="READY", action=self._open_focus),
                NavItem(key="notifs", label="NOTIFS", status="READY", action=self._open_notifications),
                NavItem(key="settings", label="SETTINGS", status="READY", action=self._open_settings),
                NavItem(key="tasks", label="TASKS", status="SYNC", action=self._open_tasks),
                NavItem(key="msgs", label="MSGS", status="SYNC", action=self._open_messages),
                NavItem(key="mail", label="MAIL", status="SYNC", action=self._open_mail),
                NavItem(key="captures", label="CAPTURES", status="", action=self._open_captures),
                NavItem(key="home", label="HOME", status="READY", action=self._open_home),
                NavItem(key="history", label="HISTORY", status="", action=self._open_history),
                NavItem(key="music", label="MUSIC", status="", action=self._open_music),
            ]
        )


    def on_enter(self):
        self._refresh_capture_count()

    def update(self, dt: float):
        self._capture_refresh_elapsed += float(dt)
        if self._capture_refresh_elapsed >= 5.0:
            self._refresh_capture_count()

        # Update time widget
        self._widget_strip.update_widget("time", value=datetime.now().strftime("%H:%M"))

        # Update unread widget from status_state
        msg_unread = int(getattr(self._status_state, "imessage_unread", 0)) if self._status_state else 0
        mail_unread = int(getattr(self._status_state, "gmail_unread", 0)) if self._status_state else 0
        self._widget_strip.update_widget("unread", value=str(msg_unread + mail_unread))

        # Advance ticker scroll
        if self._ticker_text:
            self._ticker_offset += 1

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._nav.move(1)
        elif action == "LONG_PRESS":
            if self._on_back:
                self._on_back()
        elif action == "DOUBLE_PRESS":
            self._nav.activate_focused()
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

        # Status bar (20px)
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("HOME", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))
        health = self._health_indicator()
        health_surface = self._font_small.render(health, False, BLACK)
        surface.blit(health_surface, (PHYSICAL_W - health_surface.get_width() - 6, (STATUS_BAR_H - health_surface.get_height()) // 2))

        # Widget strip (y=22, h=50)
        widget_y = STATUS_BAR_H + 2
        widget_h = 50
        self._widget_strip.render(surface, widget_y, PHYSICAL_W, widget_h, fonts=self._widget_fonts)

        # Nav list (starts below widget strip)
        y = widget_y + widget_h + 4  # y=76
        for idx, item in enumerate(self._nav.items):
            focused = idx == self._nav.focus_index
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            row_color = BLACK if focused else (WHITE if item.enabled else DIM3)
            status_color = BLACK if focused else (DIM2 if item.enabled else DIM3)
            label = item.label
            if item.key == "captures":
                label = f"CAPTURES ({self._capture_count})"
            elif item.key == "msgs":
                unread = int(getattr(self._status_state, "imessage_unread", 0)) if self._status_state else 0
                label = f"MSGS ({unread})" if unread > 0 else "MSGS"
            elif item.key == "mail":
                unread = int(getattr(self._status_state, "gmail_unread", 0)) if self._status_state else 0
                label = f"MAIL ({unread})" if unread > 0 else "MAIL"
            indicator = "> " if focused else "- "
            row = self._font_body.render(indicator + label, False, row_color)
            st = self._font_small.render(item.status, False, status_color)
            text_y = y + (ROW_H_MIN - row.get_height()) // 2
            surface.blit(row, (4, text_y))
            surface.blit(st, (PHYSICAL_W - st.get_width() - 8, text_y + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # Headlines ticker (scrolling, above hint bar)
        hint = self._font_hint.render("SHORT:NEXT · DBL:SEL · LONG:BACK", False, DIM3)
        hint_y = PHYSICAL_H - hint.get_height() - 2
        if self._ticker_text:
            ticker_y = hint_y - self._font_hint.get_height() - 4
            ticker_surf = self._font_hint.render(self._ticker_text, False, DIM2)
            ticker_w = ticker_surf.get_width()
            # Scroll offset wraps around total width + screen width
            offset = self._ticker_offset % (ticker_w + PHYSICAL_W)
            surface.blit(ticker_surf, (PHYSICAL_W - offset, ticker_y))

        # Hint bar at bottom
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, hint_y))

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

    def _open_history(self):
        # History currently maps to captures browsing.
        self._open_captures()

    def _open_music(self):
        # Reserved for upcoming music panel.
        return

    def _open_mail(self):
        if self._on_open_mail:
            self._on_open_mail()

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
    def _open_home(self):
        # Already on home panel.
        return

    def _refresh_capture_count(self):
        self._capture_refresh_elapsed = 0.0
        if not self._repository:
            self._capture_count = 0
            return
        try:
            self._capture_count = int(self._repository.get_capture_count())
        except Exception:
            self._capture_count = 0
