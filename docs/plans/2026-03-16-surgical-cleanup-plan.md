# Surgical Cleanup Sprint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove dead code, consolidate duplicated font/color systems, bump composite screen fonts, and extract shared status bar rendering.

**Architecture:** Four pillars executed in sequence: (1) dead code deletion (safe, no dependencies), (2) font/color consolidation (migrate 3 surviving ui/ components), (3) composite font bump, (4) shared status bar extraction. Each pillar has its own commit.

**Tech Stack:** Python 3, pygame, Pi Zero 2W + ST7789 240x280

**Design doc:** `docs/plans/2026-03-16-surgical-cleanup-design.md`

---

### Task 1: Delete dead audio/hardware files

**Files:**
- Delete: `device/audio/voice_pipeline.py`
- Delete: `device/hardware/battery.py`
- Delete: `device/hardware/led.py`
- Delete: `device/hardware/pi_led.py`
- Modify: `device/main.py:63-65,207-214` (remove VoicePipeline import + instantiation)

**Context:** These files are confirmed unused. `voice_pipeline.py` is marked "STATUS: Currently unused" and imported with `# noqa`. The hardware battery/LED files are superseded by `power/battery.py` and `power/leds.py`.

**Step 1: Delete the four dead files**

```bash
rm device/audio/voice_pipeline.py
rm device/hardware/battery.py
rm device/hardware/led.py
rm device/hardware/pi_led.py
```

**Step 2: Remove VoicePipeline from main.py**

Remove these lines from `device/main.py`:

Lines 63-65 (the import):
```python
# NOTE: VoicePipeline is currently unused — ChatPanel drives audio_pipeline directly.
# Kept as import for future hands-free / fob voice loop.
from device.audio.voice_pipeline import VoicePipeline  # noqa: F401
```

Lines 207-214 (the instantiation):
```python
    # VoicePipeline is instantiated here but not consumed by any screen.
    # ChatPanel uses audio_pipeline directly. Keeping for future hands-free mode.
    voice_pipeline = VoicePipeline(
        openai_key=openai_key,
        ai_send_fn=ai_send_fn,
        voice_model=os.getenv("PIPER_VOICE_MODEL", "assets/voices/en_US-ryan-low.onnx"),
    )
    screen_mgr._voice_pipeline = voice_pipeline  # stashed but unused today
```

Also remove any `openai_key` and `ai_send_fn` variables if they become unused after this removal (check if anything else references them).

**Step 3: Run tests to verify nothing breaks**

Run: `python3 -m pytest tests/test_chat_panel.py tests/test_typewriter.py tests/test_settings_wiring.py -v`
Expected: All PASS (these files were never imported by test code)

**Step 4: Commit**

```bash
git add -A
git commit -m "chore: delete dead code — VoicePipeline, hardware/battery, hardware/led"
```

---

### Task 2: Delete dummy ui/panels and unused ui/screen_manager

**Files:**
- Delete: `device/ui/panels/` (entire directory — 11 files including `__init__.py`, `base.py`)
- Delete: `device/ui/screen_manager.py`
- Modify: `device/ui/panel_registry.py` (replace with minimal placeholder panels)

**Context:** `ui/panels/` contains 9 render-only panels with hardcoded dummy data. They are only consumed by `panel_registry.py` → `CompositeScreen`. `ui/screen_manager.py` is a second ScreenManager with a different API, unused in production.

**Step 1: Delete ui/panels directory and ui/screen_manager.py**

```bash
rm -rf device/ui/panels/
rm device/ui/screen_manager.py
```

**Step 2: Rewrite panel_registry.py with minimal placeholder panels**

Replace `device/ui/panel_registry.py` with:

```python
"""Maps sidebar labels to minimal placeholder panels for composite screen."""
import pygame


class _PlaceholderPanel:
    """Minimal panel that renders the label name centered."""

    def __init__(self, label: str):
        self._label = label
        self._font = None

    def render(self, surface: pygame.Surface) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 12)
        w, h = surface.get_size()
        text = self._font.render(self._label, False, (80, 80, 80))
        surface.blit(text, ((w - text.get_width()) // 2, (h - text.get_height()) // 2))


_LABELS = ["HOME", "CHAT", "TASKS", "SETTINGS", "FOCUS", "MAIL", "MSGS", "MUSIC", "HISTORY"]


def create_right_panels() -> dict:
    """Create minimal placeholder panels keyed by sidebar label."""
    return {label: _PlaceholderPanel(label) for label in _LABELS}
```

**Step 3: Run tests**

Run: `python3 -m pytest tests/ --ignore=tests/test_audio_wm8960.py --ignore=tests/test_boot_sequence.py --ignore=tests/test_composite_screen.py -x 2>&1 | tail -5`
Expected: All PASS (no test imports from ui/panels/)

**Step 4: Commit**

```bash
git add -A
git commit -m "chore: delete dummy ui/panels + unused ui/screen_manager"
```

---

### Task 3: Migrate font/color constants to display/tokens.py

**Files:**
- Modify: `device/display/tokens.py` (add font size constants + gray colors)
- Modify: `device/display/theme.py` (add `get_font()` wrapper for backward compat)
- Modify: `device/ui/components/sidebar.py` (update imports)
- Modify: `device/ui/components/status_bar.py` (update imports)
- Modify: `device/ui/components/hint_bar.py` (update imports)
- Delete: `device/ui/fonts.py`
- Delete: `device/ui/font_sizes.py`

**Context:** Three surviving `ui/components/` files import from `ui/fonts.py` and `ui/font_sizes.py`. We migrate these constants into the canonical `display/tokens.py` and `display/theme.py`, then delete the old files.

**Step 1: Add font size constants to display/tokens.py**

Add after the existing `FONT_SIZES` dict in `device/display/tokens.py`:

```python
# Font size named constants (migrated from ui/font_sizes.py)
FONT_SIZE_TIME_LARGE = 24
FONT_SIZE_TIMER = 20
FONT_SIZE_TITLE = 16
FONT_SIZE_BODY = 12
FONT_SIZE_SIDEBAR_ITEM = 12
FONT_SIZE_CAPTION = 10
FONT_SIZE_SMALL = 10
FONT_SIZE_HINT = 8
FONT_SIZE_STATUS_BAR = 10
FONT_SIZE_PANEL_HEADER = 12
```

**Step 2: Add gray colors to display/tokens.py**

Add after existing color constants:

```python
# Extended grays (migrated from ui/panels/base.py)
GRAY_08 = (8, 8, 8)
GRAY_0A = (10, 10, 10)
GRAY_11 = (17, 17, 17)
GRAY_1A = (26, 26, 26)
GRAY_22 = (34, 34, 34)
GRAY_33 = (51, 51, 51)
GRAY_44 = (68, 68, 68)
GRAY_55 = (85, 85, 85)
GRAY_66 = (102, 102, 102)
GRAY_AA = (170, 170, 170)
```

**Step 3: Add get_font() to display/theme.py**

Add to `device/display/theme.py`:

```python
from functools import lru_cache

@lru_cache(maxsize=16)
def get_font(size: int) -> pygame.font.Font:
    """Load a font at the given pixel size, with fallback to system monospace."""
    from display.tokens import FONT_PATH
    try:
        return pygame.font.Font(FONT_PATH, size)
    except Exception:
        return pygame.font.SysFont("monospace", size)
```

**Step 4: Update sidebar.py imports**

In `device/ui/components/sidebar.py`, replace:
```python
from device.ui.fonts import get_font
from device.ui.font_sizes import SIDEBAR_ITEM
from device.ui.panels.base import WHITE, BLACK, GRAY_444, GRAY_AAA, GRAY_080808, GRAY_0A
```
With:
```python
from device.display.theme import get_font
from device.display.tokens import FONT_SIZE_SIDEBAR_ITEM as SIDEBAR_ITEM, WHITE, BLACK, GRAY_44, GRAY_AA, GRAY_08, GRAY_0A
```

And update color references: `GRAY_444` → `GRAY_44`, `GRAY_AAA` → `GRAY_AA`, `GRAY_080808` → `GRAY_08`.

**Step 5: Update status_bar.py imports**

In `device/ui/components/status_bar.py`, replace:
```python
from device.ui.fonts import get_font
from device.ui.font_sizes import STATUS_BAR
from device.ui.panels.base import WHITE, BLACK
```
With:
```python
from device.display.theme import get_font
from device.display.tokens import FONT_SIZE_STATUS_BAR as STATUS_BAR, WHITE, BLACK
```

**Step 6: Update hint_bar.py imports**

In `device/ui/components/hint_bar.py`, replace:
```python
from device.ui.fonts import get_font
from device.ui.font_sizes import HINT
from device.ui.panels.base import GRAY_111, GRAY_0A
```
With:
```python
from device.display.theme import get_font
from device.display.tokens import FONT_SIZE_HINT as HINT, GRAY_11, GRAY_0A
```

And update: `GRAY_111` → `GRAY_11`.

**Step 7: Delete old files**

```bash
rm device/ui/fonts.py device/ui/font_sizes.py
```

**Step 8: Run tests**

Run: `python3 -m pytest tests/test_chat_panel.py tests/test_settings_wiring.py -v`
Expected: All PASS

**Step 9: Commit**

```bash
git add -A
git commit -m "refactor: consolidate font/color constants into display/tokens.py + display/theme.py"
```

---

### Task 4: Bump composite screen font sizes

**Files:**
- Modify: `device/ui/components/sidebar.py` (bump SIDEBAR_ITEM from 12 → 14)
- Modify: `device/ui/components/sidebar.py` (adjust ITEM_H from 27 → 26 if needed for 9 items to fit)

**Context:** User wants slightly larger fonts on the composite home screen. Sidebar currently uses 12px. Bump to 14px. Verify 9 items × item_height still fits in the 208px available height.

**Step 1: Calculate fit**

9 items at 14px font need ~7px padding each side = 28px per item. 9 × 28 = 252px. Available = 208px. That's too tall. Try 26px per item: 9 × 26 = 234px. Still too tall. Try 23px: 9 × 23 = 207px. Perfect fit.

So: bump font to 14px, reduce ITEM_H to 23, reduce PAD_Y to 4.

**Step 2: Update sidebar.py**

Change in `device/ui/components/sidebar.py`:
```python
ITEM_H = 23
FONT_SIZE = 14  # bumped from 12
PAD_X = 7
PAD_Y = 4  # reduced from 7 to fit 9 items
```

Remove the `SIDEBAR_ITEM` import since we're now using a literal.

**Step 3: Test visually on device**

Deploy and verify: all 9 sidebar items visible, no overlap, text readable at 14px.

**Step 4: Commit**

```bash
git add device/ui/components/sidebar.py
git commit -m "style: bump sidebar font from 12px to 14px for readability"
```

---

### Task 5: Extract shared status bar renderer

**Files:**
- Create: `device/display/panel_status_bar.py`
- Modify: `device/screens/panels/messages.py` (delegate to shared renderer)
- Modify: `device/screens/panels/mail.py` (delegate to shared renderer)

**Context:** `messages.py` and `mail.py` both have `_render_status_bar()` methods with near-identical logic: white bar, title, battery%. Extract to shared utility.

**Step 1: Read the two implementations to understand differences**

Read `device/screens/panels/messages.py` around line 200-220 and `device/screens/panels/mail.py` around line 184-205 to capture exact code.

**Step 2: Create shared renderer**

Create `device/display/panel_status_bar.py`:

```python
"""Shared status bar renderer for list-style panels."""
import pygame
from display.tokens import BLACK, WHITE, PHYSICAL_W, STATUS_BAR_H


def render_panel_status_bar(
    surface: pygame.Surface,
    title: str,
    font: pygame.font.Font,
    right_text: str = "",
) -> None:
    """Render a white status bar with title (left) and optional right text."""
    pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
    title_surf = font.render(title, False, BLACK)
    surface.blit(title_surf, (6, (STATUS_BAR_H - title_surf.get_height()) // 2))
    if right_text:
        right_surf = font.render(right_text, False, BLACK)
        surface.blit(right_surf, (PHYSICAL_W - right_surf.get_width() - 6,
                                   (STATUS_BAR_H - right_surf.get_height()) // 2))
```

**Step 3: Update messages.py and mail.py to use shared renderer**

Replace each panel's `_render_status_bar` call with an import and call to `render_panel_status_bar()`.

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_messages_panel.py tests/test_mail_panel.py -v`
Expected: Same results as before (4 pass, 4 pre-existing fail in mail)

**Step 5: Commit**

```bash
git add device/display/panel_status_bar.py device/screens/panels/messages.py device/screens/panels/mail.py
git commit -m "refactor: extract shared panel status bar renderer"
```

---

### Task 6: Final verification + push

**Step 1: Run full test suite**

```bash
python3 -m pytest tests/ --ignore=tests/test_audio_wm8960.py --ignore=tests/test_boot_sequence.py --ignore=tests/test_composite_screen.py -v 2>&1 | tail -20
```

Expected: All sprint-related tests pass, same pre-existing failures as before.

**Step 2: Verify no dangling imports**

```bash
grep -r "from.*ui\.panels" device/ --include="*.py" | grep -v __pycache__ | grep -v panel_registry
grep -r "from.*ui\.fonts" device/ --include="*.py" | grep -v __pycache__
grep -r "from.*ui\.font_sizes" device/ --include="*.py" | grep -v __pycache__
grep -r "from.*ui\.screen_manager" device/ --include="*.py" | grep -v __pycache__
```

Expected: All four commands return empty (no dangling imports).

**Step 3: Push**

```bash
git push
```

**Step 4: Deploy command**

```
ssh pi "cd bitos && git pull && sudo systemctl restart bitos"
```
