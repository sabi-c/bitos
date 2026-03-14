"""BITOS Home panel with button-first sidebar navigation."""
import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM2, DIM3, HAIRLINE, PHYSICAL_W, PHYSICAL_H
from display.theme import merge_runtime_ui_settings, load_ui_font
from screens.components import NavItem, VerticalNavController


class HomePanel(BaseScreen):
    """Home panel with focusable sidebar entries and action routing."""

    def __init__(
        self,
        on_open_chat=None,
        on_open_focus=None,
        on_open_notifications=None,
        on_open_settings=None,
        ui_settings: dict | None = None,
    ):
        self._on_open_chat = on_open_chat
        self._on_open_focus = on_open_focus
        self._on_open_notifications = on_open_notifications
        self._on_open_settings = on_open_settings
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
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

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        title = self._font_title.render("HOME", False, WHITE)
        surface.blit(title, (8, 8))
        pygame.draw.line(surface, HAIRLINE, (0, 24), (PHYSICAL_W, 24))

        y = 38
        for idx, item in enumerate(self._nav.items):
            row_color = WHITE if item.enabled else DIM3
            status_color = DIM2 if item.enabled else DIM3
            row = self._font_body.render(item.label, False, row_color)
            st = self._font_small.render(item.status, False, status_color)
            if idx == self._nav.focus_index:
                pygame.draw.rect(surface, WHITE, pygame.Rect(4, y - 2, PHYSICAL_W - 8, 15), width=1)
            surface.blit(row, (8, y))
            surface.blit(st, (PHYSICAL_W - st.get_width() - 8, y + 2))
            pygame.draw.line(surface, HAIRLINE, (8, y + 12), (PHYSICAL_W - 8, y + 12))
            y += 20

        hint = self._font_small.render("SEL SHORT • NEXT DOUBLE", False, DIM3)
        surface.blit(hint, (8, PHYSICAL_H - 14))

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
