"""CompositeScreen — full 240x280 layout with sidebar navigation.

Extends BaseScreen so the old ScreenManager can push/pop it.
Composes: StatusBar (20px) | Sidebar (84px left) + RightPanel (156x208) | ActionBar (20px).
All zones respect SAFE_INSET=16 to avoid corner-clipped areas.

┌─────────────────────────────────┐ 0
│          (16px inset)           │
│         STATUS BAR (20px)       │ 16
├──────────┬──────────────────────┤ 36
│ SIDEBAR  │   RIGHT PANEL       │
│  84px    │    156x208px        │
│          │  [panel.render()]   │
├──────────┴──────────────────────┤ 244
│     ACTION BAR (20px)          │
│          (16px inset)           │
└─────────────────────────────────┘ 280
"""

from __future__ import annotations

import pygame

from device.display.tokens import PHYSICAL_W, PHYSICAL_H, SIDEBAR_W, CONTENT_W, STATUS_BAR_H, SAFE_INSET
from device.ui.components.sidebar import Sidebar, ITEMS
from device.ui.components.status_bar import StatusBar
from device.ui.components.action_bar import ActionBar
from device.screens.base import BaseScreen

BLACK = (0, 0, 0)

HINT_BAR_H = 20  # Upgraded action bar height (was 12)
CONTENT_TOP = SAFE_INSET + STATUS_BAR_H  # 36
CONTENT_BOTTOM = PHYSICAL_H - SAFE_INSET - HINT_BAR_H  # 244
RIGHT_PANEL_H = CONTENT_BOTTOM - CONTENT_TOP  # 208


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
        self._action_bar = ActionBar()

        # Subsurface for right panel rendering (156x208)
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

        # Status bar at top (full width, 20px, below SAFE_INSET)
        self._status_bar.render(surface, y=SAFE_INSET, width=PHYSICAL_W)

        # Sidebar on left (84px wide, from y=36 to y=244)
        self._sidebar.render(surface, x=0, y=CONTENT_TOP, height=RIGHT_PANEL_H)

        # Right panel (156x208, positioned at x=84, y=36)
        label = self._sidebar.items[self._sidebar.selected_index]
        panel = self._right_panels.get(label)
        if panel is not None:
            self._right_surface.fill(BLACK)
            panel.render(self._right_surface)
            surface.blit(self._right_surface, (SIDEBAR_W, CONTENT_TOP))

        # Action bar at bottom (full width, 20px)
        self._action_bar.render(surface, y=CONTENT_BOTTOM, width=PHYSICAL_W)

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
        elif action == "DOUBLE_PRESS":
            label = self._sidebar.items[self._sidebar.selected_index]
            opener = self._panel_openers.get(label)
            if opener is not None:
                opener()
        # LONG_PRESS is no-op at root level

    def handle_input(self, event: pygame.event.Event) -> None:
        """Keyboard support for desktop testing."""
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_DOWN, pygame.K_j):
            self.handle_action("SHORT_PRESS")
        elif event.key in (pygame.K_UP, pygame.K_k):
            self.handle_action("TRIPLE_PRESS")
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.handle_action("DOUBLE_PRESS")

    # ── Hints / breadcrumb ───────────────────────────────────────

    def get_hint(self) -> str:
        if self._action_bar.text:
            return self._action_bar.text
        return " · ".join(label for _, label in self._action_bar.actions)

    def get_breadcrumb(self) -> str:
        return self._sidebar.items[self._sidebar.selected_index]
