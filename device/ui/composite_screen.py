"""CompositeScreen — full 240x280 layout with sidebar navigation.

Extends BaseScreen so the old ScreenManager can push/pop it.
Composes: StatusBar (18px top) | Sidebar (84px left) + RightPanel (156x250) | HintBar (12px bottom).

┌─────────────────────────────────┐ 0
│         STATUS BAR (18px)       │
├──────────┬──────────────────────┤ 18
│ SIDEBAR  │   RIGHT PANEL       │
│  84px    │    156x250px        │
│          │  [panel.render()]   │
├──────────┴──────────────────────┤ 268
│      HINT BAR (12px)           │
└─────────────────────────────────┘ 280
"""

from __future__ import annotations

import pygame

from device.display.tokens import PHYSICAL_W, PHYSICAL_H, SIDEBAR_W, CONTENT_W, STATUS_BAR_H
from device.ui.components.sidebar import Sidebar, ITEMS
from device.ui.components.status_bar import StatusBar
from device.ui.components.hint_bar import HintBar
from device.screens.base import BaseScreen

BLACK = (0, 0, 0)

HINT_BAR_H = 12
RIGHT_PANEL_H = PHYSICAL_H - STATUS_BAR_H - HINT_BAR_H  # 250


class CompositeScreen(BaseScreen):
    """Full-screen composite: status bar + sidebar + right panel + hint bar."""

    SCREEN_NAME = "COMPOSITE"
    _owns_status_bar = True

    def __init__(
        self,
        panel_openers: dict | None = None,
        status_state=None,
        right_panels: dict | None = None,
    ):
        super().__init__()
        self._panel_openers = panel_openers or {}
        self._status_state = status_state
        self._right_panels = right_panels or {}

        self._sidebar = Sidebar()
        self._status_bar = StatusBar()
        self._hint_bar = HintBar()

        # Subsurface for right panel rendering (156x250)
        self._right_surface = pygame.Surface((CONTENT_W, RIGHT_PANEL_H))

    # ── Lifecycle ────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        label = self._sidebar.items[self._sidebar.selected_index]
        panel = self._right_panels.get(label)
        if panel is not None and hasattr(panel, "update"):
            panel.update(dt)

    # ── Rendering ────────────────────────────────────────────────

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)

        # Status bar at top (full width, 18px)
        self._status_bar.render(surface, y=0, width=PHYSICAL_W)

        # Sidebar on left (84px wide, from y=18 to y=268)
        self._sidebar.render(surface, x=0, y=STATUS_BAR_H, height=RIGHT_PANEL_H)

        # Right panel (156x250, positioned at x=84, y=18)
        label = self._sidebar.items[self._sidebar.selected_index]
        panel = self._right_panels.get(label)
        if panel is not None:
            self._right_surface.fill(BLACK)
            panel.render(self._right_surface)
            surface.blit(self._right_surface, (SIDEBAR_W, STATUS_BAR_H))

        # Hint bar at bottom (full width, 12px)
        self._hint_bar.render(surface, y=PHYSICAL_H - HINT_BAR_H, width=PHYSICAL_W)

    def draw(self, surface: pygame.Surface) -> None:
        """Alias for ScreenManager compatibility (calls render)."""
        self.render(surface)

    # ── Input ────────────────────────────────────────────────────

    def handle_action(self, action: str) -> None:
        n = len(self._sidebar.items)
        if action == "SHORT_PRESS":
            self._sidebar.selected_index = (self._sidebar.selected_index + 1) % n
        elif action == "TRIPLE_PRESS":
            self._sidebar.selected_index = (self._sidebar.selected_index - 1) % n
        elif action == "LONG_PRESS":
            label = self._sidebar.items[self._sidebar.selected_index]
            opener = self._panel_openers.get(label)
            if opener is not None:
                opener()
        # DOUBLE_PRESS is no-op at root level

    def handle_input(self, event: pygame.event.Event) -> None:
        """Keyboard support for desktop testing."""
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_DOWN, pygame.K_j):
            self.handle_action("SHORT_PRESS")
        elif event.key in (pygame.K_UP, pygame.K_k):
            self.handle_action("TRIPLE_PRESS")
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.handle_action("LONG_PRESS")

    # ── Hints / breadcrumb ───────────────────────────────────────

    def get_hint(self) -> str:
        return self._hint_bar.text

    def get_breadcrumb(self) -> str:
        return self._sidebar.items[self._sidebar.selected_index]
