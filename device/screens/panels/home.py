"""BITOS Home panel with button-first sidebar navigation."""
import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM2, DIM3, HAIRLINE, PHYSICAL_W, PHYSICAL_H, STATUS_BAR_H, ROW_H_MIN
from display.theme import merge_runtime_ui_settings, load_ui_font
from screens.components import NavItem, VerticalNavController


class HomePanel(BaseScreen):
    """Home panel with focusable sidebar entries and action routing."""
    _owns_status_bar = True

    def __init__(
        self,
        on_open_chat=None,
        on_open_focus=None,
        on_open_notifications=None,
        on_open_settings=None,
        on_show_shade=None,
        ui_settings: dict | None = None,
        startup_health: dict | None = None,
    ):
        self._on_open_chat = on_open_chat
        self._on_open_focus = on_open_focus
        self._on_open_notifications = on_open_notifications
        self._on_open_settings = on_open_settings
        self._on_show_shade = on_show_shade
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
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
            ]
        )

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._nav.activate_focused()
        elif action == "DOUBLE_PRESS":
            self._open_shade()
        elif action == "LONG_PRESS":
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

        # ── Status bar: 18px, inverted (white bg, black text) ──
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("HOME", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))
        health = self._health_indicator()
        health_surface = self._font_small.render(health, False, BLACK)
        surface.blit(health_surface, (PHYSICAL_W - health_surface.get_width() - 6, (STATUS_BAR_H - health_surface.get_height()) // 2))

        # ── Rows: 26px minimum, inverted focus, scroll window ──
        y_start = STATUS_BAR_H + 2
        hint_h = 12  # approximate hint bar height
        available_h = PHYSICAL_H - y_start - hint_h
        max_visible = max(1, available_h // ROW_H_MIN)
        items = self._nav.items
        focus = self._nav.focus_index
        start = max(0, min(focus - max_visible + 1, len(items) - max_visible))
        if focus < start:
            start = focus
        visible = items[start:start + max_visible]

        y = y_start
        for idx_offset, item in enumerate(visible):
            idx = start + idx_offset
            focused = idx == focus
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            row_color = BLACK if focused else (WHITE if item.enabled else DIM3)
            status_color = BLACK if focused else (DIM2 if item.enabled else DIM3)
            row = self._font_body.render(item.label, False, row_color)
            st = self._font_small.render(item.status, False, status_color)
            text_y = y + (ROW_H_MIN - row.get_height()) // 2
            surface.blit(row, (8, text_y))
            surface.blit(st, (PHYSICAL_W - st.get_width() - 8, text_y + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # ── Key hint bar: 4px font, spec format ──
        hint = self._font_hint.render("SHORT:SEL \u00b7 LONG:NEXT \u00b7 DBL:SHADE", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    def _open_chat(self):
        if self._on_open_chat:
            self._on_open_chat()

    def _open_focus(self):
        if self._on_open_focus:
            self._on_open_focus()

    def _open_notifications(self):
        if self._on_open_notifications:
            self._on_open_notifications()

    def _open_settings(self):
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
