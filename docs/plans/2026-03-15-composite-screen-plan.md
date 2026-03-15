# CompositeScreen Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the full-screen HomePanel with a CompositeScreen that renders the new HTML-reference UI (StatusBar + Sidebar + right panel + HintBar) while keeping all existing panel logic working.

**Architecture:** CompositeScreen extends BaseScreen so the old ScreenManager accepts it. It composes the 240x280 layout from new components. When a sidebar item is selected, it still pushes the old full-screen panel onto the ScreenManager stack (same as today). This means Phase 1 gives us the new sidebar/home look immediately, and sub-panels are migrated incrementally later.

**Tech Stack:** Python, pygame, existing BaseScreen/ScreenManager infrastructure

---

### Task 1: Create CompositeScreen class

**Files:**
- Create: `device/ui/composite_screen.py`
- Test: `tests/test_composite_screen.py`

**Step 1: Write the failing test**

```python
# tests/test_composite_screen.py
import unittest
from unittest.mock import MagicMock, patch
import pygame

pygame.init()


class TestCompositeScreen(unittest.TestCase):
    def setUp(self):
        self.surface = pygame.Surface((240, 280))

    @patch("device.ui.composite_screen.get_font")
    def test_render_draws_status_bar_sidebar_hint(self, mock_font):
        mock_font.return_value = pygame.font.SysFont("monospace", 8)
        from device.ui.composite_screen import CompositeScreen

        cs = CompositeScreen(panel_openers={})
        cs.render(self.surface)
        # Status bar area (top 18px) should have white pixels
        self.assertEqual(self.surface.get_at((120, 9))[:3], (255, 255, 255))
        # Sidebar border (x=83) should have white pixels
        self.assertEqual(self.surface.get_at((83, 100))[:3], (255, 255, 255))

    @patch("device.ui.composite_screen.get_font")
    def test_short_press_moves_sidebar_selection(self, mock_font):
        mock_font.return_value = pygame.font.SysFont("monospace", 8)
        from device.ui.composite_screen import CompositeScreen

        cs = CompositeScreen(panel_openers={})
        self.assertEqual(cs._sidebar.selected_index, 0)
        cs.handle_action("SHORT_PRESS")
        self.assertEqual(cs._sidebar.selected_index, 1)

    @patch("device.ui.composite_screen.get_font")
    def test_long_press_calls_panel_opener(self, mock_font):
        mock_font.return_value = pygame.font.SysFont("monospace", 8)
        from device.ui.composite_screen import CompositeScreen

        opener = MagicMock()
        cs = CompositeScreen(panel_openers={"CHAT": opener})
        cs._sidebar.selected_index = 1  # CHAT
        cs.handle_action("LONG_PRESS")
        opener.assert_called_once()

    @patch("device.ui.composite_screen.get_font")
    def test_sidebar_wraps_at_bounds(self, mock_font):
        mock_font.return_value = pygame.font.SysFont("monospace", 8)
        from device.ui.composite_screen import CompositeScreen

        cs = CompositeScreen(panel_openers={})
        n = len(cs._sidebar.items)
        for _ in range(n):
            cs.handle_action("SHORT_PRESS")
        self.assertEqual(cs._sidebar.selected_index, 0)  # wrapped

    @patch("device.ui.composite_screen.get_font")
    def test_triple_press_moves_sidebar_up(self, mock_font):
        mock_font.return_value = pygame.font.SysFont("monospace", 8)
        from device.ui.composite_screen import CompositeScreen

        cs = CompositeScreen(panel_openers={})
        cs._sidebar.selected_index = 2
        cs.handle_action("TRIPLE_PRESS")
        self.assertEqual(cs._sidebar.selected_index, 1)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/seb/bitos/device && python -m pytest ../tests/test_composite_screen.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'device.ui.composite_screen'`

**Step 3: Write minimal implementation**

```python
# device/ui/composite_screen.py
"""CompositeScreen: Sidebar + StatusBar + right panel + HintBar layout.

Extends BaseScreen so the old ScreenManager accepts it.
Renders the new HTML-reference UI components into 240x280.
"""

import pygame

from screens.base import BaseScreen
from display.tokens import PHYSICAL_W, PHYSICAL_H, SIDEBAR_W, CONTENT_W, STATUS_BAR_H
from device.ui.components.sidebar import Sidebar, ITEMS
from device.ui.components.status_bar import StatusBar
from device.ui.components.hint_bar import HintBar
from device.ui.fonts import get_font

# Right panel area dimensions
PANEL_X = SIDEBAR_W  # 84
PANEL_Y = STATUS_BAR_H  # 18
HINT_H = 12  # hint bar height
PANEL_H = PHYSICAL_H - STATUS_BAR_H - HINT_H  # 250


class CompositeScreen(BaseScreen):
    """Root screen: sidebar nav + right-panel content + chrome."""

    _owns_status_bar = True  # We render our own status bar

    def __init__(self, panel_openers: dict, status_state=None,
                 right_panels: dict | None = None):
        """
        Args:
            panel_openers: Map sidebar label -> callable that pushes old panel
                           e.g. {"CHAT": open_chat, "TASKS": open_tasks}
            status_state: StatusState for status bar data
            right_panels: Map sidebar label -> new BasePanel instance for right area
        """
        self._panel_openers = panel_openers
        self._status_state = status_state
        self._sidebar = Sidebar()
        self._status_bar = StatusBar()
        self._hint_bar = HintBar()
        self._right_panels = right_panels or {}
        self._panel_surface = pygame.Surface((CONTENT_W, PANEL_H))

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def update(self, dt: float):
        # Update the active right panel if it has an update method
        label = self._sidebar.items[self._sidebar.selected_index]
        panel = self._right_panels.get(label)
        if panel and hasattr(panel, "update"):
            panel.update(dt)

    def handle_action(self, action: str):
        n = len(self._sidebar.items)
        if action == "SHORT_PRESS":
            self._sidebar.selected_index = (self._sidebar.selected_index + 1) % n
        elif action == "TRIPLE_PRESS":
            self._sidebar.selected_index = (self._sidebar.selected_index - 1) % n
        elif action == "LONG_PRESS":
            label = self._sidebar.items[self._sidebar.selected_index]
            opener = self._panel_openers.get(label)
            if opener:
                opener()
        elif action == "DOUBLE_PRESS":
            # Already at root — no-op or show shade
            pass

    def handle_input(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_DOWN, pygame.K_j):
            self.handle_action("SHORT_PRESS")
        elif event.key in (pygame.K_UP, pygame.K_k):
            self.handle_action("TRIPLE_PRESS")
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.handle_action("LONG_PRESS")

    def render(self, surface: pygame.Surface):
        surface.fill((0, 0, 0))

        # Status bar (full width, top 18px)
        if self._status_state:
            self._status_bar.title = "BITOS"
            # Could pull status from status_state here
        self._status_bar.render(surface, y=0, width=PHYSICAL_W)

        # Sidebar (left 84px, below status bar)
        self._sidebar.render(surface, x=0, y=STATUS_BAR_H,
                             height=PHYSICAL_H - STATUS_BAR_H - HINT_H)

        # Right panel (156px wide, below status bar, above hint)
        label = self._sidebar.items[self._sidebar.selected_index]
        panel = self._right_panels.get(label)
        if panel:
            self._panel_surface.fill((0, 0, 0))
            panel.render(self._panel_surface)
            surface.blit(self._panel_surface, (PANEL_X, PANEL_Y))

        # Hint bar (full width, bottom)
        self._hint_bar.render(surface, y=PHYSICAL_H - HINT_H, width=PHYSICAL_W)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/seb/bitos/device && python -m pytest ../tests/test_composite_screen.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add device/ui/composite_screen.py tests/test_composite_screen.py
git commit -m "feat: add CompositeScreen — sidebar+statusbar+panel+hintbar layout"
```

---

### Task 2: Create panel registry

**Files:**
- Create: `device/ui/panel_registry.py`

**Step 1: Write the registry**

```python
# device/ui/panel_registry.py
"""Maps sidebar labels to new render-only panel classes."""

from device.ui.panels.home import HomePanel
from device.ui.panels.chat import ChatPanel
from device.ui.panels.tasks import TasksPanel
from device.ui.panels.settings import SettingsPanel
from device.ui.panels.focus import FocusPanel
from device.ui.panels.mail import MailPanel
from device.ui.panels.messages import MessagesPanel
from device.ui.panels.music import MusicPanel
from device.ui.panels.history import HistoryPanel


def create_right_panels() -> dict:
    """Create instances of all render-only right panels, keyed by sidebar label."""
    return {
        "HOME": HomePanel(),
        "CHAT": ChatPanel(),
        "TASKS": TasksPanel(),
        "SETTINGS": SettingsPanel(),
        "FOCUS": FocusPanel(),
        "MAIL": MailPanel(),
        "MSGS": MessagesPanel(),
        "MUSIC": MusicPanel(),
        "HISTORY": HistoryPanel(),
    }
```

**Step 2: Commit**

```bash
git add device/ui/panel_registry.py
git commit -m "feat: add panel registry mapping sidebar labels to render panels"
```

---

### Task 3: Wire CompositeScreen into main.py

**Files:**
- Modify: `device/main.py:35-36,360-378`

**Step 1: Update imports in main.py**

Replace:
```python
from screens.panels.home import HomePanel
```
With:
```python
from screens.panels.home import HomePanel  # keep for fallback
from device.ui.composite_screen import CompositeScreen
from device.ui.panel_registry import create_right_panels
```

**Step 2: Replace on_home() function**

Replace the `on_home()` function (lines 360-378) with:

```python
    right_panels = create_right_panels()

    def on_home():
        panel_openers = {
            "HOME": lambda: None,  # already showing home
            "CHAT": open_chat,
            "TASKS": open_tasks,
            "SETTINGS": open_settings,
            "FOCUS": open_focus,
            "MAIL": open_mail,
            "MSGS": open_messages,
            "MUSIC": lambda: None,  # not yet implemented
            "HISTORY": open_captures,
        }
        home = CompositeScreen(
            panel_openers=panel_openers,
            status_state=status_state,
            right_panels=right_panels,
        )
        screen_mgr.replace(home)
```

Note: All `open_*` functions still push old full-screen panels onto ScreenManager. The ONLY visual change is that the root/home screen now shows the new sidebar + right panel layout instead of the old full-width list.

**Step 3: Run device to verify**

Run: `cd /Users/seb/bitos/device && python main.py`
Expected: Device boots, shows new sidebar layout on home screen. Selecting any menu item opens the old panel (full screen). DOUBLE_PRESS returns to the new home layout.

**Step 4: Commit**

```bash
git add device/main.py
git commit -m "feat: wire CompositeScreen as root screen, replacing old HomePanel"
```

---

### Task 4: Fix font import path for device context

**Files:**
- Modify: `device/ui/fonts.py` — font path may need to be relative to device/ working dir
- Modify: `device/ui/panels/base.py` — import path adjustment if needed

**Step 1: Check font path resolution**

The new panels import `from device.ui.fonts import get_font` but when running from `device/` as cwd, the module path is `device.ui.fonts`. Check if this resolves correctly.

Run: `cd /Users/seb/bitos/device && python -c "from device.ui.composite_screen import CompositeScreen; print('OK')"`

If import fails, fix the import paths. The old panels use relative imports (`from screens.base import BaseScreen`), so the new code needs to match that convention.

Likely fix: Change imports in `device/ui/composite_screen.py` from `from device.ui.components.sidebar import ...` to `from ui.components.sidebar import ...` (relative to device/ cwd).

**Step 2: Commit any fixes**

```bash
git add -u
git commit -m "fix: adjust import paths for device working directory"
```

---

### Task 5: Add pyaudio to requirements + fix stub endpoints

**Files:**
- Modify: `requirements-device.txt` (or `requirements.txt`)
- Modify: `server/main.py` — `/dashboard` and `/brief` endpoints

**Step 1: Add pyaudio dependency**

```bash
echo "pyaudio>=0.2.14" >> requirements-device.txt
```

**Step 2: Fix stub endpoints in server/main.py**

Find the `/dashboard` and `/brief` routes that return `{"status": "not_implemented"}` and implement minimal versions that return useful data.

**Step 3: Commit**

```bash
git add requirements-device.txt server/main.py
git commit -m "chore: add pyaudio dep, implement /dashboard and /brief endpoints"
```

---

### Task 6: Run full test suite and push

**Step 1: Run all tests**

Run: `cd /Users/seb/bitos && python -m pytest tests/ -v --tb=short 2>&1 | tail -30`

**Step 2: Fix any new failures**

**Step 3: Final commit and push**

```bash
git push
```
