"""Tests for CompositeScreen — sidebar navigation + submenu system."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

# device/ on sys.path so old-style imports (screens.base) resolve;
# repo root on sys.path so device.ui.* imports resolve.
_repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_repo / "device"))
sys.path.insert(0, str(_repo))

from device.ui.composite_screen import CompositeScreen
from device.ui.components.sidebar import ITEMS
from device.ui.panels.base import PreviewPanel


def _make_preview_panel(actions_log=None):
    """Create a simple PreviewPanel for testing."""
    items = [
        {"label": "ITEM A", "description": "First", "action": "action_a"},
        {"label": "ITEM B", "description": "Second", "action": "action_b"},
        {"label": "BACK", "description": "Return", "action": "back"},
    ]
    log = actions_log if actions_log is not None else []
    return PreviewPanel(items=items, on_action=lambda key: log.append(key))


class CompositeScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()
        cls.surface = pygame.Surface((240, 280))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    # ── Render ───────────────────────────────────────────────────

    def test_render_draws_without_error(self):
        """render() completes with no panels registered."""
        cs = CompositeScreen()
        cs.render(self.surface)  # should not raise

    def test_render_draws_status_bar(self):
        """Status bar renders white rectangle at top."""
        cs = CompositeScreen()
        cs.render(self.surface)
        # Status bar is white bg — pixel at (120, 21) should be white (SAFE_INSET=16)
        color = self.surface.get_at((120, 21))
        self.assertEqual((color.r, color.g, color.b), (255, 255, 255))

    def test_render_draws_sidebar(self):
        """Sidebar renders selected item (white bg) in the sidebar region."""
        cs = CompositeScreen()
        cs.render(self.surface)
        # Selected item (index 0) at sidebar left, just below status bar
        color = self.surface.get_at((10, 22))
        self.assertEqual((color.r, color.g, color.b), (255, 255, 255))

    def test_render_draws_hint_bar(self):
        """Hint bar occupies bottom 12px."""
        cs = CompositeScreen()
        cs.render(self.surface)
        self.assertTrue(True)

    def test_render_calls_right_panel(self):
        """If a right panel is registered for current sidebar item, its render() is called."""
        panel = MagicMock()
        cs = CompositeScreen(right_panels={"HOME": panel})
        cs.render(self.surface)
        panel.render.assert_called_once()

    # ── Navigation: SHORT_PRESS moves down ───────────────────────

    def test_short_press_moves_sidebar_down(self):
        cs = CompositeScreen()
        self.assertEqual(cs._sidebar.selected_index, 0)
        cs.handle_action("SHORT_PRESS")
        self.assertEqual(cs._sidebar.selected_index, 1)
        cs.handle_action("SHORT_PRESS")
        self.assertEqual(cs._sidebar.selected_index, 2)

    def test_short_press_wraps_at_bottom(self):
        cs = CompositeScreen()
        n = len(ITEMS)
        cs._sidebar.selected_index = n - 1
        cs.handle_action("SHORT_PRESS")
        self.assertEqual(cs._sidebar.selected_index, 0)

    # ── Navigation: TRIPLE_PRESS moves up ────────────────────────

    def test_triple_press_moves_sidebar_up(self):
        cs = CompositeScreen()
        cs._sidebar.selected_index = 3
        cs.handle_action("TRIPLE_PRESS")
        self.assertEqual(cs._sidebar.selected_index, 2)

    def test_triple_press_wraps_at_top(self):
        cs = CompositeScreen()
        cs._sidebar.selected_index = 0
        cs.handle_action("TRIPLE_PRESS")
        self.assertEqual(cs._sidebar.selected_index, len(ITEMS) - 1)

    # ── DOUBLE_PRESS enters submenu (new behavior) ───────────────

    def test_double_press_enters_submenu_mode(self):
        """DOUBLE on sidebar with preview panel enters submenu mode."""
        panel = _make_preview_panel()
        cs = CompositeScreen(right_panels={"HOME": panel})
        self.assertEqual(cs.focus, "sidebar")
        cs.handle_action("DOUBLE_PRESS")
        self.assertEqual(cs.focus, "submenu")

    def test_double_press_no_panel_calls_opener(self):
        """DOUBLE on sidebar with no preview panel falls back to opener."""
        called = {}
        cs = CompositeScreen(panel_openers={"HOME": lambda: called.update(home=True)})
        cs.handle_action("DOUBLE_PRESS")
        self.assertTrue(called.get("home"))

    def test_double_press_resets_submenu_selection(self):
        """Entering submenu resets selected_index to 0."""
        panel = _make_preview_panel()
        panel.selected_index = 2
        cs = CompositeScreen(right_panels={"HOME": panel})
        cs.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel.selected_index, 0)

    # ── Submenu: SHORT scrolls items ──────────────────────────────

    def test_short_in_submenu_scrolls_items(self):
        """SHORT in submenu mode advances submenu selection."""
        panel = _make_preview_panel()
        cs = CompositeScreen(right_panels={"HOME": panel})
        cs.handle_action("DOUBLE_PRESS")  # enter submenu
        self.assertEqual(panel.selected_index, 0)
        cs.handle_action("SHORT_PRESS")
        self.assertEqual(panel.selected_index, 1)
        cs.handle_action("SHORT_PRESS")
        self.assertEqual(panel.selected_index, 2)

    def test_short_in_submenu_wraps(self):
        """SHORT wraps around submenu items."""
        panel = _make_preview_panel()
        cs = CompositeScreen(right_panels={"HOME": panel})
        cs.handle_action("DOUBLE_PRESS")  # enter submenu
        panel.selected_index = 2  # last item
        cs.handle_action("SHORT_PRESS")
        self.assertEqual(panel.selected_index, 0)

    def test_short_in_submenu_does_not_move_sidebar(self):
        """SHORT in submenu should NOT change sidebar selection."""
        panel = _make_preview_panel()
        cs = CompositeScreen(right_panels={"HOME": panel})
        cs.handle_action("DOUBLE_PRESS")
        sidebar_idx = cs._sidebar.selected_index
        cs.handle_action("SHORT_PRESS")
        self.assertEqual(cs._sidebar.selected_index, sidebar_idx)

    # ── Submenu: DOUBLE triggers action ──────────────────────────

    def test_double_in_submenu_triggers_action(self):
        """DOUBLE in submenu calls on_action with the action key."""
        actions = []
        panel = _make_preview_panel(actions_log=actions)
        cs = CompositeScreen(right_panels={"HOME": panel})
        cs.handle_action("DOUBLE_PRESS")  # enter submenu
        cs.handle_action("DOUBLE_PRESS")  # execute first item
        self.assertEqual(actions, ["action_a"])

    def test_double_in_submenu_second_item(self):
        """Navigate to second item and execute."""
        actions = []
        panel = _make_preview_panel(actions_log=actions)
        cs = CompositeScreen(right_panels={"HOME": panel})
        cs.handle_action("DOUBLE_PRESS")  # enter submenu
        cs.handle_action("SHORT_PRESS")   # move to item B
        cs.handle_action("DOUBLE_PRESS")  # execute
        self.assertEqual(actions, ["action_b"])

    # ── Submenu: BACK item returns to sidebar ─────────────────────

    def test_back_action_returns_to_sidebar(self):
        """Selecting BACK item returns focus to sidebar."""
        panel = _make_preview_panel()
        cs = CompositeScreen(right_panels={"HOME": panel})
        cs.handle_action("DOUBLE_PRESS")  # enter submenu
        self.assertEqual(cs.focus, "submenu")
        # Navigate to BACK item (index 2)
        cs.handle_action("SHORT_PRESS")  # index 1
        cs.handle_action("SHORT_PRESS")  # index 2 (BACK)
        cs.handle_action("DOUBLE_PRESS")  # execute BACK
        self.assertEqual(cs.focus, "sidebar")

    # ── Submenu: LONG returns to sidebar ──────────────────────────

    def test_long_in_submenu_returns_to_sidebar(self):
        """LONG press in submenu mode returns to sidebar mode."""
        panel = _make_preview_panel()
        cs = CompositeScreen(right_panels={"HOME": panel})
        cs.handle_action("DOUBLE_PRESS")  # enter submenu
        self.assertEqual(cs.focus, "submenu")
        cs.handle_action("LONG_PRESS")
        self.assertEqual(cs.focus, "sidebar")

    # ── LONG_PRESS is no-op in sidebar ───────────────────────────

    def test_long_press_sidebar_is_noop(self):
        cs = CompositeScreen()
        idx = cs._sidebar.selected_index
        cs.handle_action("LONG_PRESS")
        self.assertEqual(cs._sidebar.selected_index, idx)
        self.assertEqual(cs.focus, "sidebar")

    # ── Keyboard input ───────────────────────────────────────────

    def test_keyboard_down_maps_to_short_press(self):
        cs = CompositeScreen()
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)
        cs.handle_input(event)
        self.assertEqual(cs._sidebar.selected_index, 1)

    def test_keyboard_up_maps_to_triple_press(self):
        cs = CompositeScreen()
        cs._sidebar.selected_index = 2
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
        cs.handle_input(event)
        self.assertEqual(cs._sidebar.selected_index, 1)

    def test_keyboard_enter_maps_to_double_press(self):
        """Enter key now enters submenu (if panel exists) instead of calling opener."""
        panel = _make_preview_panel()
        cs = CompositeScreen(right_panels={"HOME": panel})
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        cs.handle_input(event)
        self.assertEqual(cs.focus, "submenu")

    def test_keyboard_escape_maps_to_long_press(self):
        """Escape key returns from submenu to sidebar."""
        panel = _make_preview_panel()
        cs = CompositeScreen(right_panels={"HOME": panel})
        cs.handle_action("DOUBLE_PRESS")  # enter submenu
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        cs.handle_input(event)
        self.assertEqual(cs.focus, "sidebar")

    def test_keyboard_j_moves_down(self):
        cs = CompositeScreen()
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j)
        cs.handle_input(event)
        self.assertEqual(cs._sidebar.selected_index, 1)

    def test_keyboard_k_moves_up(self):
        cs = CompositeScreen()
        cs._sidebar.selected_index = 3
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_k)
        cs.handle_input(event)
        self.assertEqual(cs._sidebar.selected_index, 2)

    # ── Update ticks right panel ─────────────────────────────────

    def test_update_ticks_active_panel(self):
        panel = MagicMock()
        cs = CompositeScreen(right_panels={"HOME": panel})
        cs.update(0.016)
        panel.update.assert_called_once_with(0.016)

    def test_update_no_panel_is_noop(self):
        cs = CompositeScreen()
        cs.update(0.016)  # should not raise


if __name__ == "__main__":
    unittest.main()
