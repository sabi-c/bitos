# BITOS UI Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Monocraft font with hot-swap picker, apply 1-bit design system visual polish (row indicators, consistent borders), and rework the chat panel to be voice-first with an action menu.

**Architecture:** Three pillars implemented sequentially. Pillar 1 (fonts) modifies the token/theme layer and adds a settings panel. Pillar 2 (visual polish) updates rendering across all nav-based screens. Pillar 3 (chat) rewrites the chat panel layout with action menu and fixes the back-out bug.

**Tech Stack:** Python 3.11, pygame, SQLite (DeviceRepository), SSE streaming

---

## Pillar 1: Font System

### Task 1: Download Monocraft font and add font registry

**Files:**
- Create: `device/assets/fonts/Monocraft.ttf`
- Modify: `device/display/tokens.py:26-28`
- Test: `tests/test_font_registry.py`

**Step 1: Download Monocraft.ttf**

```bash
curl -L -o device/assets/fonts/Monocraft.ttf \
  "https://cdn.jsdelivr.net/gh/IdreesInc/Monocraft@main/dist/Monocraft-ttf/Monocraft.ttf"
```

Verify file exists and is > 50KB:
```bash
ls -la device/assets/fonts/Monocraft.ttf
```

**Step 2: Add font registry to tokens.py**

Replace lines 26-28 in `device/display/tokens.py`:

```python
# ── Typography ─────────────────────────────────────────────────
FONT_REGISTRY = {
    "press_start_2p": "assets/fonts/PressStart2P.ttf",
    "monocraft": "assets/fonts/Monocraft.ttf",
}
DEFAULT_FONT_FAMILY = "press_start_2p"
FONT_NAME = "PressStart2P"
FONT_PATH = FONT_REGISTRY[DEFAULT_FONT_FAMILY]
```

**Step 3: Write the failing test**

Create `tests/test_font_registry.py`:

```python
"""Tests for font registry and multi-font support."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from display.tokens import FONT_REGISTRY, DEFAULT_FONT_FAMILY


class FontRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_registry_has_press_start(self):
        self.assertIn("press_start_2p", FONT_REGISTRY)

    def test_registry_has_monocraft(self):
        self.assertIn("monocraft", FONT_REGISTRY)

    def test_default_is_press_start(self):
        self.assertEqual(DEFAULT_FONT_FAMILY, "press_start_2p")

    def test_all_font_files_exist(self):
        for family, path in FONT_REGISTRY.items():
            full = Path(__file__).resolve().parents[1] / "device" / path
            self.assertTrue(full.exists(), f"Font file missing for {family}: {full}")

    def test_all_fonts_load_in_pygame(self):
        for family, path in FONT_REGISTRY.items():
            full = str(Path(__file__).resolve().parents[1] / "device" / path)
            font = pygame.font.Font(full, 12)
            self.assertIsNotNone(font)
            # Verify it can render text
            surface = font.render("TEST", False, (255, 255, 255))
            self.assertGreater(surface.get_width(), 0)


if __name__ == "__main__":
    unittest.main()
```

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_font_registry.py -v
```

Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add device/assets/fonts/Monocraft.ttf device/display/tokens.py tests/test_font_registry.py
git commit -m "feat: add Monocraft font and font registry in tokens.py"
```

---

### Task 2: Update theme.py to use font registry for multi-font loading

**Files:**
- Modify: `device/display/theme.py:1-69`
- Test: `tests/test_font_registry.py` (add tests)

**Step 1: Write the failing tests**

Append to `tests/test_font_registry.py`:

```python
from display.theme import load_ui_font, flush_font_cache, _FONT_CACHE


class FontHotSwapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_load_press_start(self):
        settings = {"font_family": "press_start_2p", "font_scale": 1.0,
                     "font_size_overrides": {"body": 12}}
        font = load_ui_font("body", settings)
        self.assertIsNotNone(font)

    def test_load_monocraft(self):
        settings = {"font_family": "monocraft", "font_scale": 1.0,
                     "font_size_overrides": {"body": 12}}
        font = load_ui_font("body", settings)
        self.assertIsNotNone(font)

    def test_different_families_return_different_fonts(self):
        ps = load_ui_font("body", {"font_family": "press_start_2p", "font_scale": 1.0,
                                    "font_size_overrides": {"body": 12}})
        mc = load_ui_font("body", {"font_family": "monocraft", "font_scale": 1.0,
                                    "font_size_overrides": {"body": 12}})
        # Different font objects (different underlying font file)
        self.assertIsNot(ps, mc)

    def test_flush_font_cache_clears_all(self):
        load_ui_font("body", {"font_family": "press_start_2p", "font_scale": 1.0,
                               "font_size_overrides": {"body": 12}})
        self.assertGreater(len(_FONT_CACHE), 0)
        flush_font_cache()
        self.assertEqual(len(_FONT_CACHE), 0)

    def test_unknown_family_falls_back_to_monospace(self):
        font = load_ui_font("body", {"font_family": "nonexistent_font", "font_scale": 1.0,
                                      "font_size_overrides": {"body": 12}})
        self.assertIsNotNone(font)
```

**Step 2: Run tests — expect failures for `flush_font_cache` and monocraft loading**

```bash
python3 -m pytest tests/test_font_registry.py -v
```

**Step 3: Update theme.py**

Replace `device/display/theme.py` with:

```python
"""Runtime UI theme helpers (fed by backend settings)."""
from __future__ import annotations

import pygame

_FONT_CACHE: dict[tuple[str, int], pygame.font.Font] = {}

from display.tokens import FONT_REGISTRY, DEFAULT_FONT_FAMILY, FONT_SIZES, PAD_ROW

DEFAULT_RUNTIME_UI_SETTINGS = {
    "font_family": DEFAULT_FONT_FAMILY,
    "font_scale": 1.0,
    "font_size_overrides": {
        "title": FONT_SIZES["title"],
        "body": FONT_SIZES["body"],
        "small": FONT_SIZES["small"],
        "hint": FONT_SIZES["hint"],
    },
    "layout_density": "comfy",
    "sidebar_width": 84,
}


def merge_runtime_ui_settings(incoming: dict | None) -> dict:
    merged = {
        "font_family": DEFAULT_RUNTIME_UI_SETTINGS["font_family"],
        "font_scale": DEFAULT_RUNTIME_UI_SETTINGS["font_scale"],
        "font_size_overrides": dict(DEFAULT_RUNTIME_UI_SETTINGS["font_size_overrides"]),
        "layout_density": DEFAULT_RUNTIME_UI_SETTINGS["layout_density"],
        "sidebar_width": DEFAULT_RUNTIME_UI_SETTINGS["sidebar_width"],
    }

    if not isinstance(incoming, dict):
        return merged

    for key in ["font_family", "font_scale", "layout_density", "sidebar_width"]:
        if key in incoming:
            merged[key] = incoming[key]

    if isinstance(incoming.get("font_size_overrides"), dict):
        merged["font_size_overrides"].update(incoming["font_size_overrides"])

    return merged


def flush_font_cache() -> None:
    """Clear all cached fonts. Call after font_family or font_scale changes."""
    _FONT_CACHE.clear()


def ui_font_size(role: str, ui_settings: dict) -> int:
    base = ui_settings.get("font_size_overrides", {}).get(role, FONT_SIZES[role])
    scale = ui_settings.get("font_scale", 1.0)
    return max(5, int(round(base * float(scale))))


def load_ui_font(role: str, ui_settings: dict) -> pygame.font.Font:
    size = ui_font_size(role, ui_settings)
    family = ui_settings.get("font_family", DEFAULT_FONT_FAMILY)
    cache_key = (family, size)

    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]

    font_path = FONT_REGISTRY.get(family)
    if font_path:
        try:
            font = pygame.font.Font(font_path, size)
        except (FileNotFoundError, OSError):
            font = pygame.font.SysFont("monospace", size)
    else:
        font = pygame.font.SysFont("monospace", size)

    _FONT_CACHE[cache_key] = font
    return font


def ui_line_height(font: pygame.font.Font, ui_settings: dict) -> int:
    extra = 2 if ui_settings.get("layout_density") == "compact" else PAD_ROW
    return font.get_height() + extra
```

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_font_registry.py -v
```

Expected: All 10 tests PASS.

**Step 5: Commit**

```bash
git add device/display/theme.py tests/test_font_registry.py
git commit -m "feat: multi-font loading via registry + flush_font_cache for hot-swap"
```

---

### Task 3: Add FontPickerPanel to settings

**Files:**
- Modify: `device/screens/panels/settings.py` (update existing `FontScalePanel` → combine into `FontPickerPanel`)
- Modify: `device/main.py` (wire opener)
- Test: `tests/test_font_registry.py` (add panel test)

**Step 1: Write the failing test**

Append to `tests/test_font_registry.py`:

```python
import tempfile
from storage.repository import DeviceRepository


class FontPickerPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = DeviceRepository(db_path=str(Path(self.tmp.name) / "bitos.db"))
        self.repo.initialize()
        self.went_back = False

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_font_is_press_start(self):
        from screens.panels.settings import FontPickerPanel
        panel = FontPickerPanel(repository=self.repo, on_back=lambda: None)
        self.assertEqual(panel._current_family, "press_start_2p")

    def test_short_press_cycles_font(self):
        from screens.panels.settings import FontPickerPanel
        panel = FontPickerPanel(repository=self.repo, on_back=lambda: None)
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._index, 1)  # monocraft

    def test_double_press_saves_and_goes_back(self):
        from screens.panels.settings import FontPickerPanel
        panel = FontPickerPanel(
            repository=self.repo,
            on_back=lambda: setattr(self, 'went_back', True),
        )
        panel.handle_action("SHORT_PRESS")  # move to monocraft
        panel.handle_action("DOUBLE_PRESS")  # select
        self.assertEqual(self.repo.get_setting("font_family", default="press_start_2p"), "monocraft")
        self.assertTrue(self.went_back)

    def test_long_press_goes_back_without_saving(self):
        from screens.panels.settings import FontPickerPanel
        panel = FontPickerPanel(
            repository=self.repo,
            on_back=lambda: setattr(self, 'went_back', True),
        )
        panel.handle_action("SHORT_PRESS")  # move to monocraft
        panel.handle_action("LONG_PRESS")  # back without saving
        self.assertEqual(self.repo.get_setting("font_family", default="press_start_2p"), "press_start_2p")
        self.assertTrue(self.went_back)
```

**Step 2: Implement FontPickerPanel**

Replace the existing `FontScalePanel` class in `device/screens/panels/settings.py` with a combined `FontPickerPanel` that handles both font family and scale:

```python
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
            row = self._font_body.render(label, False, row_color)
            text_y = y + (ROW_H_MIN - row.get_height()) // 2
            surface.blit(row, (8, text_y))
            if is_active:
                badge_color = BLACK if focused else DIM2
                badge = self._font_small.render("ACTIVE", False, badge_color)
                surface.blit(badge, (PHYSICAL_W - badge.get_width() - 8, text_y + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # Preview line using selected font
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
```

Also update the SettingsPanel:
- Rename `on_open_font_scale` → `on_open_font_picker`
- Rename nav item key `font_scale` → `font` with label `FONT`
- Update status to show current font family name

Update `device/main.py`:
- Replace `FontScalePanel` import with `FontPickerPanel`
- Replace `open_font_scale` with `open_font_picker`
- Read `font_family` from repository into `ui_settings` alongside `font_scale`

**Step 3: Run tests**

```bash
python3 -m pytest tests/test_font_registry.py -v
```

Expected: All 14 tests PASS.

**Step 4: Commit**

```bash
git add device/screens/panels/settings.py device/main.py tests/test_font_registry.py
git commit -m "feat: FontPickerPanel with hot-swap — Press Start 2P + Monocraft"
```

---

## Pillar 2: Visual Polish

### Task 4: Add row indicators to VerticalNavController rendering

**Files:**
- Modify: `device/screens/panels/settings.py` (render method patterns)
- Modify: `device/screens/panels/home.py` (render method)
- Modify: `device/screens/panels/notifications.py` (render method)
- Modify: `device/screens/panels/tasks.py` (render method)
- Modify: `device/screens/panels/captures.py` (render method)

**Context:** Every screen that renders nav rows currently uses plain text. We need to add `\u25b8` (▸) prefix on focused items and `\u25cb` (○) on default items to match the 1-bit design system.

**Step 1: Update the rendering pattern**

In every panel's render loop where rows are drawn, change:

```python
# BEFORE:
row = self._font_body.render(item.label, False, row_color)
surface.blit(row, (8, text_y))

# AFTER:
indicator = "\u25b8 " if focused else "\u25cb "
row = self._font_body.render(indicator + item.label, False, row_color)
surface.blit(row, (4, text_y))
```

Apply this to:
- `device/screens/panels/settings.py` — SettingsPanel.render() row loop (line ~165)
- `device/screens/panels/home.py` — HomePanel.render() row loop
- `device/screens/panels/tasks.py` — render() row loop
- `device/screens/panels/captures.py` — render() row loop
- `device/screens/panels/notifications.py` — render() row loop

Also apply to picker panels (ModelPickerPanel, AgentModePanel, SleepTimerPanel, FontPickerPanel) for consistency.

**Note:** Disabled rows use dimmed text with `○` indicator. The integrations header row (`─ INTEGRATIONS ─`) should NOT get an indicator.

**Step 2: Run existing tests to verify no breakage**

```bash
python3 -m pytest tests/test_composite_screen.py tests/test_settings_wiring.py tests/test_pin_lock.py -v
```

Expected: All pass (rendering changes don't affect logic tests).

**Step 3: Commit**

```bash
git add device/screens/panels/settings.py device/screens/panels/home.py device/screens/panels/tasks.py device/screens/panels/captures.py device/screens/panels/notifications.py
git commit -m "feat: add row indicators (▸ focused, ○ default) across all nav screens"
```

---

### Task 5: Add loading skeleton states for async panels

**Files:**
- Modify: `device/screens/panels/tasks.py`
- Modify: `device/screens/panels/messages.py`
- Modify: `device/screens/panels/mail.py`

**Context:** When tasks, messages, or mail are loading from the backend, show a skeleton shimmer pattern instead of a blank screen. The 1-bit design system defines a loading state as gray rectangles with a step blink animation.

**Step 1: Add loading state rendering**

In each async panel, add a `_loading` boolean set to `True` during fetch, `False` after. When `_loading is True`, render 3-4 skeleton rows:

```python
def _render_skeleton(self, surface: pygame.Surface, y: int, count: int = 4):
    """Render skeleton loading rows."""
    blink = (pygame.time.get_ticks() // 800) % 2 == 0
    color = DIM3 if blink else DIM4
    for _ in range(count):
        pygame.draw.rect(surface, color, (8, y + 4, PHYSICAL_W - 48, 8))
        pygame.draw.rect(surface, HAIRLINE, (PHYSICAL_W - 36, y + 4, 28, 8))
        pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
        y += ROW_H_MIN
```

**Step 2: Run tests**

```bash
python3 -m pytest tests/ --ignore=tests/test_audio_wm8960.py --ignore=tests/test_boot_sequence.py --ignore=tests/test_mail_panel.py -q
```

**Step 3: Commit**

```bash
git add device/screens/panels/tasks.py device/screens/panels/messages.py device/screens/panels/mail.py
git commit -m "feat: add skeleton loading states for async panels (tasks, messages, mail)"
```

---

## Pillar 3: Chat Panel Rework

### Task 6: Rework chat panel with action menu and voice-first flow

**Files:**
- Modify: `device/screens/panels/chat.py` (major rework)
- Test: `tests/test_chat_panel.py`

**Context:** Replace the current input-bar-at-bottom layout with a voice-first action menu. The bottom of the screen shows 3 selectable items: SPEAK, ACTIONS, BACK. Templates move under ACTIONS. The message area takes up most of the screen.

**Step 1: Write the failing tests**

Create `tests/test_chat_panel.py`:

```python
"""Tests for ChatPanel action menu and voice-first flow."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.chat import ChatPanel


class ChatActionMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()
        cls.surface = pygame.Surface((240, 280))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_panel(self, **kwargs):
        client = MagicMock()
        client.chat = MagicMock(return_value=iter(["hello"]))
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=None)
        repo.get_latest_session = MagicMock(return_value=None)
        return ChatPanel(client=client, repository=repo, on_back=kwargs.get("on_back"), audio_pipeline=kwargs.get("audio"))

    def test_action_menu_starts_at_speak(self):
        panel = self._make_panel()
        self.assertEqual(panel._action_index, 0)  # SPEAK

    def test_short_press_cycles_action_menu(self):
        panel = self._make_panel()
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._action_index, 1)  # ACTIONS

    def test_short_press_wraps_around(self):
        panel = self._make_panel()
        panel.handle_action("SHORT_PRESS")  # ACTIONS
        panel.handle_action("SHORT_PRESS")  # BACK
        panel.handle_action("SHORT_PRESS")  # wraps to SPEAK
        self.assertEqual(panel._action_index, 0)

    def test_double_press_on_back_calls_on_back(self):
        called = []
        panel = self._make_panel(on_back=lambda: called.append(True))
        panel._action_index = 2  # BACK
        panel.handle_action("DOUBLE_PRESS")
        self.assertTrue(called)

    def test_long_press_always_goes_back(self):
        called = []
        panel = self._make_panel(on_back=lambda: called.append(True))
        panel.handle_action("LONG_PRESS")
        self.assertTrue(called)

    def test_render_without_error(self):
        panel = self._make_panel()
        panel.render(self.surface)  # should not raise


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_chat_panel.py -v
```

Expected: FAIL (no `_action_index` attribute yet).

**Step 3: Rework ChatPanel**

Key changes to `device/screens/panels/chat.py`:

1. Add `_action_index = 0` and `ACTION_ITEMS = ["SPEAK", "ACTIONS", "BACK"]` to `__init__`
2. Remove the input bar at the bottom (text input via keyboard only, voice is primary)
3. Add action menu rendering at bottom (3 rows above hint bar)
4. `handle_action` rework:
   - `SHORT_PRESS`: cycle `_action_index` through 0→1→2→0
   - `DOUBLE_PRESS` on index 0 (SPEAK): start voice capture
   - `DOUBLE_PRESS` on index 1 (ACTIONS): toggle template/smart-action sub-menu
   - `DOUBLE_PRESS` on index 2 (BACK): call `_on_back()`
   - `LONG_PRESS`: always call `_on_back()` (safety net)
   - `TRIPLE_PRESS`: new chat (clear messages)
5. Message area rendering: `STATUS_BAR_H` to `PHYSICAL_H - action_menu_height - hint_height`
6. User messages prefixed with `> ` in DIM2, assistant messages in WHITE
7. Keep streaming, retry, LED, audio, session persistence logic unchanged

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_chat_panel.py -v
```

Expected: All 6 tests PASS.

**Step 5: Commit**

```bash
git add device/screens/panels/chat.py tests/test_chat_panel.py
git commit -m "feat: rework chat panel — voice-first action menu (SPEAK/ACTIONS/BACK)"
```

---

### Task 7: Add recording indicator with volume meter

**Files:**
- Modify: `device/screens/panels/chat.py` (render method)

**Context:** When recording, show a visual indicator: pulsing red dot + "REC" in the status bar, and a simple volume meter bar in the message area.

**Step 1: Add recording state rendering**

In `ChatPanel.render()`, when `self._status_detail == "recording..."`:

```python
# Status bar: show ●REC (pulsing)
if self._status_detail == "recording...":
    blink = (pygame.time.get_ticks() // 400) % 2 == 0
    if blink:
        rec_text = self._font_small.render("\u25cf REC", False, WHITE)
        surface.blit(rec_text, (PHYSICAL_W - rec_text.get_width() - 6,
                                (STATUS_BAR_H - rec_text.get_height()) // 2))
```

**Step 2: Run all tests**

```bash
python3 -m pytest tests/test_chat_panel.py tests/test_font_registry.py tests/test_settings_wiring.py -v
```

Expected: All pass.

**Step 3: Commit**

```bash
git add device/screens/panels/chat.py
git commit -m "feat: add pulsing REC indicator in chat status bar during voice recording"
```

---

### Task 8: Final integration test and push

**Step 1: Run full test suite**

```bash
python3 -m pytest tests/ --ignore=tests/test_audio_wm8960.py --ignore=tests/test_boot_sequence.py --ignore=tests/test_mail_panel.py -v
```

Expected: All tests pass.

**Step 2: Push**

```bash
git push origin main
```

**Step 3: Deploy on Pi**

SSH to Pi and run:
```bash
cd ~/bitos && git fetch origin && git reset --hard origin/main && sudo systemctl restart bitos-device
```
