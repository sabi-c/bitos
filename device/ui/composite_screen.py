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

Navigation state machine:
  SIDEBAR mode (default):
    SHORT  → next sidebar item
    TRIPLE → prev sidebar item
    DOUBLE → enter SUBMENU mode for selected item
    LONG   → no-op

  SUBMENU mode:
    SHORT  → next submenu item (routed to preview panel)
    DOUBLE → execute submenu action (routed to preview panel)
    LONG   → back to SIDEBAR mode
"""

from __future__ import annotations

from enum import Enum

import pygame

from device.display.tokens import PHYSICAL_W, PHYSICAL_H, SIDEBAR_W, CONTENT_W, STATUS_BAR_H, SAFE_INSET
from device.ui.components.sidebar import Sidebar, ITEMS
from device.ui.components.status_bar import StatusBar
from device.ui.components.action_bar import ActionBar
from device.screens.base import BaseScreen

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

HINT_BAR_H = 20  # Upgraded action bar height (was 12)
CONTENT_TOP = SAFE_INSET + STATUS_BAR_H  # 36
CONTENT_BOTTOM = PHYSICAL_H - SAFE_INSET - HINT_BAR_H  # 244
RIGHT_PANEL_H = CONTENT_BOTTOM - CONTENT_TOP  # 208

# ── Transition constants ──────────────────────────────────────
SLIDE_OFFSET_PX = 10        # Starting offset for slide-in (pixels)
SLIDE_DURATION_S = 0.20     # 200ms — ~3 frames at 15 FPS
FLASH_DURATION_S = 0.15     # 150ms sidebar highlight flash
SIDEBAR_SCROLL_DURATION_S = 0.12  # 120ms smooth scroll between sidebar items


class _Focus(Enum):
    SIDEBAR = "sidebar"
    SUBMENU = "submenu"


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
        self._focus = _Focus.SIDEBAR
        self._update_action_bar_hint()

        # Subsurface for right panel rendering (156x208)
        self._right_surface = pygame.Surface((CONTENT_W, RIGHT_PANEL_H))

        # ── Transition state ──────────────────────────────────────
        # Panel slide: "enter" = slide-left into submenu, "exit" = slide-right back
        self._slide_active = False
        self._slide_progress = 1.0   # 0.0 → 1.0 (done)
        self._slide_direction = "enter"  # "enter" or "exit"
        # Sidebar flash: countdown timer for highlight flash on scroll
        self._flash_timer = 0.0
        # Sidebar smooth scroll: animates between sidebar item positions
        self._sidebar_scroll_active = False
        self._sidebar_scroll_progress = 1.0
        self._sidebar_scroll_from = 0  # previous selected index
        self._sidebar_scroll_to = 0    # target selected index

    @property
    def focus(self) -> str:
        """Current focus mode as string: 'sidebar' or 'submenu'."""
        return self._focus.value

    # ── Lifecycle ────────────────────────────────────────────────

    def set_unread_count(self, count: int) -> None:
        """Set the notification badge count on the status bar."""
        self._status_bar.set_unread_count(count)

    def update(self, dt: float) -> None:
        # Advance panel slide transition
        if self._slide_active:
            self._slide_progress += dt / SLIDE_DURATION_S
            if self._slide_progress >= 1.0:
                self._slide_progress = 1.0
                self._slide_active = False

        # Advance sidebar flash
        if self._flash_timer > 0.0:
            self._flash_timer = max(0.0, self._flash_timer - dt)

        # Advance sidebar smooth scroll
        if self._sidebar_scroll_active:
            self._sidebar_scroll_progress += dt / SIDEBAR_SCROLL_DURATION_S
            if self._sidebar_scroll_progress >= 1.0:
                self._sidebar_scroll_progress = 1.0
                self._sidebar_scroll_active = False

        # Update breadcrumb in status bar
        self._update_breadcrumb()

        if not self._sidebar.items:
            return
        idx = self._sidebar.selected_index % len(self._sidebar.items)
        label = self._sidebar.items[idx]
        panel = self._right_panels.get(label)
        if panel is not None and hasattr(panel, "update"):
            panel.update(dt)

    # ── Breadcrumb ────────────────────────────────────────────────

    def _update_breadcrumb(self) -> None:
        """Update status bar breadcrumb based on current focus and sidebar selection."""
        if not self._sidebar.items:
            self._status_bar.set_breadcrumb("")
            return
        idx = self._sidebar.selected_index % len(self._sidebar.items)
        section = self._sidebar.items[idx]
        if self._focus == _Focus.SUBMENU:
            panel = self._right_panels.get(section)
            if panel and hasattr(panel, "selected_index") and hasattr(panel, "items"):
                si = panel.selected_index
                if 0 <= si < len(panel.items):
                    sub_label = panel.items[si].get("label", "")
                    self._status_bar.set_breadcrumb(f"{section}>{sub_label}")
                    return
            self._status_bar.set_breadcrumb(section)
        else:
            self._status_bar.set_breadcrumb(section)

    # ── Transitions ───────────────────────────────────────────────

    def _start_slide(self, direction: str) -> None:
        """Kick off a slide transition. direction: 'enter' or 'exit'."""
        self._slide_active = True
        self._slide_progress = 0.0
        self._slide_direction = direction

    def _start_sidebar_scroll(self, from_idx: int, to_idx: int) -> None:
        """Kick off a smooth scroll animation between sidebar items."""
        self._sidebar_scroll_active = True
        self._sidebar_scroll_progress = 0.0
        self._sidebar_scroll_from = from_idx
        self._sidebar_scroll_to = to_idx

    def _sidebar_highlight_y_offset(self) -> float:
        """Compute interpolated Y offset for the sidebar highlight during scroll."""
        if not self._sidebar_scroll_active:
            return 0.0
        # Ease-out: fast start, gentle settle
        t = self._sidebar_scroll_progress
        eased = 1.0 - (1.0 - t) ** 2
        from device.ui.components.sidebar import ITEM_H
        from_y = self._sidebar_scroll_from * ITEM_H
        to_y = self._sidebar_scroll_to * ITEM_H
        return from_y + (to_y - from_y) * eased - to_y  # delta from target

    def _snap_slide(self) -> None:
        """Instantly finish any in-progress slide (interruptibility)."""
        self._slide_active = False
        self._slide_progress = 1.0

    def _slide_offset_x(self) -> int:
        """Compute horizontal pixel offset for current slide transition."""
        if not self._slide_active:
            return 0
        # Ease-out quadratic: fast start, gentle settle
        remaining = (1.0 - self._slide_progress) ** 2
        offset = int(SLIDE_OFFSET_PX * remaining)
        if self._slide_direction == "exit":
            return -offset  # slide out to the right
        # Entering submenu: content slides in from right
        return offset

    # ── Rendering ────────────────────────────────────────────────

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)

        # Status bar at top (full width, 20px, below SAFE_INSET)
        self._status_bar.render(surface, y=SAFE_INSET, width=PHYSICAL_W)

        # Sidebar on left (84px wide, from y=36 to y=244)
        scroll_offset = self._sidebar_highlight_y_offset()
        self._sidebar.render(surface, x=0, y=CONTENT_TOP, height=RIGHT_PANEL_H,
                             highlight_y_offset=scroll_offset)

        # Sidebar flash overlay: brief white highlight fading on newly selected item
        if self._flash_timer > 0.0:
            from device.ui.components.sidebar import ITEM_H
            flash_alpha = int(80 * (self._flash_timer / FLASH_DURATION_S))
            flash_y = CONTENT_TOP + self._sidebar.selected_index * ITEM_H
            flash_surf = pygame.Surface((SIDEBAR_W - 2, ITEM_H))
            flash_surf.fill(WHITE)
            flash_surf.set_alpha(flash_alpha)
            surface.blit(flash_surf, (0, flash_y))

        # Right panel (156x208, positioned at x=84, y=36)
        # Apply slide offset during transitions
        if not self._sidebar.items:
            return
        label = self._sidebar.items[self._sidebar.selected_index % len(self._sidebar.items)]
        panel = self._right_panels.get(label)
        if panel is not None:
            self._right_surface.fill(BLACK)
            panel.render(self._right_surface)
            offset_x = self._slide_offset_x()
            surface.blit(self._right_surface, (SIDEBAR_W + offset_x, CONTENT_TOP))

        # Action bar at bottom (full width, 20px)
        self._action_bar.render(surface, y=CONTENT_BOTTOM, width=PHYSICAL_W)

    def draw(self, surface: pygame.Surface) -> None:
        """Alias for ScreenManager compatibility (calls render)."""
        self.render(surface)

    # ── Input ────────────────────────────────────────────────────

    def _active_panel(self):
        """Return the preview panel for the currently selected sidebar item."""
        if not self._sidebar.items:
            return None
        idx = self._sidebar.selected_index % len(self._sidebar.items)
        label = self._sidebar.items[idx]
        return self._right_panels.get(label)

    def handle_action(self, action: str) -> None:
        if self._focus == _Focus.SIDEBAR:
            self._handle_sidebar_action(action)
        else:
            self._handle_submenu_action(action)

    def _handle_sidebar_action(self, action: str) -> None:
        n = len(self._sidebar.items)
        if n == 0:
            return
        if action == "SHORT_PRESS":
            old_idx = self._sidebar.selected_index
            self._sidebar.selected_index = (self._sidebar.selected_index + 1) % n
            self._start_sidebar_scroll(old_idx, self._sidebar.selected_index)
            self._flash_timer = FLASH_DURATION_S
        elif action == "TRIPLE_PRESS":
            old_idx = self._sidebar.selected_index
            self._sidebar.selected_index = (self._sidebar.selected_index - 1) % n
            self._start_sidebar_scroll(old_idx, self._sidebar.selected_index)
            self._flash_timer = FLASH_DURATION_S
        elif action == "DOUBLE_PRESS":
            # Enter submenu mode if panel exists
            panel = self._active_panel()
            if panel is not None and hasattr(panel, "handle_action"):
                self._focus = _Focus.SUBMENU
                self._update_action_bar_hint()
                self._snap_slide()       # cancel any in-progress slide
                self._start_slide("enter")
                # Reset submenu selection and scroll when entering
                if hasattr(panel, "selected_index"):
                    panel.selected_index = 0
                if hasattr(panel, "_scroll_offset"):
                    panel._scroll_offset = 0
            else:
                # Fallback: call opener directly (legacy behavior)
                label = self._sidebar.items[self._sidebar.selected_index]
                opener = self._panel_openers.get(label)
                if opener is not None:
                    opener()
        # LONG_PRESS is no-op at root level

    def _exit_submenu(self) -> None:
        """Return to sidebar mode and clear submenu highlight."""
        panel = self._active_panel()
        if panel is not None and hasattr(panel, "selected_index"):
            panel.selected_index = -1
        self._focus = _Focus.SIDEBAR
        self._update_action_bar_hint()
        self._snap_slide()           # cancel any in-progress slide
        self._start_slide("exit")

    def _handle_submenu_action(self, action: str) -> None:
        if action == "LONG_PRESS":
            # If panel is in a recording state, route LONG to panel (cancel), not exit
            panel = self._active_panel()
            if panel and hasattr(panel, '_rec_state'):
                from device.ui.panels.chat_preview import RecState
                if panel._rec_state in (RecState.RECORDING, RecState.ERROR):
                    panel.handle_action(action)
                    self._update_rec_action_hints(panel)
                    return
            self._exit_submenu()
            return

        panel = self._active_panel()
        if panel is not None and hasattr(panel, "handle_action"):
            # Check if the action is "back" before routing
            if action == "DOUBLE_PRESS" and hasattr(panel, "items") and hasattr(panel, "selected_index"):
                idx = panel.selected_index
                if 0 <= idx < len(panel.items):
                    item = panel.items[idx]
                    if item.get("action") == "back":
                        self._exit_submenu()
                        return
            panel.handle_action(action)
            # Update hints if panel has recording state
            if hasattr(panel, '_rec_state'):
                self._update_rec_action_hints(panel)

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
        elif event.key == pygame.K_ESCAPE:
            self.handle_action("LONG_PRESS")

    # ── Action bar hints ────────────────────────────────────────

    _SIDEBAR_ACTIONS = [
        ("tap", "NAV"),
        ("double", "SELECT"),
    ]

    _SUBMENU_ACTIONS = [
        ("tap", "NAV"),
        ("double", "GO"),
        ("hold", "BACK"),
    ]

    _REC_ACTIONS = [
        ("tap", "STOP"),
        ("hold", "CANCEL"),
    ]

    _REC_ERROR_ACTIONS = [
        ("tap", "RETRY"),
        ("hold", "CANCEL"),
    ]

    def _update_action_bar_hint(self) -> None:
        """Set action bar icons+labels based on current focus mode."""
        if self._focus == _Focus.SUBMENU:
            # Check for recording state on active panel
            panel = self._active_panel()
            if panel and hasattr(panel, '_rec_state'):
                self._update_rec_action_hints(panel)
                return
            self._action_bar.set_actions(self._SUBMENU_ACTIONS)
        else:
            self._action_bar.set_actions(self._SIDEBAR_ACTIONS)

    def _update_rec_action_hints(self, panel) -> None:
        """Update action bar for recording states."""
        from device.ui.panels.chat_preview import RecState
        if panel._rec_state == RecState.RECORDING:
            self._action_bar.set_actions(self._REC_ACTIONS)
        elif panel._rec_state in (RecState.TRANSCRIBING, RecState.LAUNCHING):
            self._action_bar.set_actions([])
        elif panel._rec_state == RecState.ERROR:
            self._action_bar.set_actions(self._REC_ERROR_ACTIONS)
        else:
            self._action_bar.set_actions(self._SUBMENU_ACTIONS)

    # ── Hints / breadcrumb ───────────────────────────────────────

    def get_hint(self) -> str:
        if self._action_bar.text:
            return self._action_bar.text
        return " · ".join(label for _, label in self._action_bar.actions)

    def get_breadcrumb(self) -> str:
        if not self._sidebar.items:
            return ""
        return self._sidebar.items[self._sidebar.selected_index % len(self._sidebar.items)]
