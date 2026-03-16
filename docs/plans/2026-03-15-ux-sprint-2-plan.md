# BITOS UX Sprint 2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix voice chat flow with gesture-driven input modes, fix display corner clipping, upgrade hint bar to action bar, and add typewriter response rendering.

**Architecture:** Five pillars implemented in sequence: (1) safe area system (foundational layout constant), (2) action bar upgrade (replaces hint bar), (3) chat input state machine (replaces action menu with gesture-driven modes), (4) typewriter renderer (progressive text reveal), (5) flicker investigation. Each pillar builds on prior work but is independently shippable.

**Tech Stack:** Python 3, pygame, threading.Event, Pi Zero 2W + ST7789 240x280

**Design doc:** `docs/plans/2026-03-15-ux-sprint-2-design.md`

---

### Task 1: Safe Area — Add SAFE_INSET constant and update corner mask

**Files:**
- Modify: `device/display/tokens.py:14` (CORNER_RADIUS line)
- Modify: `device/display/corner_mask.py:10` (CORNER_RADIUS line)
- Test: `tests/test_safe_area.py`

**Context:** Content gets clipped by the display's rounded corners. Currently `corner_mask.py` hardcodes an 8px radius, and `tokens.py` has `CORNER_RADIUS = 20` (inconsistent). We unify on 16px and add a `SAFE_INSET` constant that all layout code will reference.

**Step 1: Write the failing test**

Create `tests/test_safe_area.py`:

```python
"""Tests for safe area constants and corner mask."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))


class SafeAreaConstantsTests(unittest.TestCase):
    def test_safe_inset_exists_in_tokens(self):
        from display.tokens import SAFE_INSET
        self.assertEqual(SAFE_INSET, 16)

    def test_corner_radius_matches_safe_inset(self):
        from display.tokens import CORNER_RADIUS, SAFE_INSET
        self.assertEqual(CORNER_RADIUS, SAFE_INSET)

    def test_corner_mask_uses_tokens_radius(self):
        from display.corner_mask import CORNER_RADIUS as MASK_RADIUS
        from display.tokens import CORNER_RADIUS as TOKENS_RADIUS
        self.assertEqual(MASK_RADIUS, TOKENS_RADIUS)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_safe_area.py -v`
Expected: FAIL — `SAFE_INSET` doesn't exist yet, and `CORNER_RADIUS` values mismatch.

**Step 3: Update tokens.py**

In `device/display/tokens.py`, replace line 14:
```python
CORNER_RADIUS = 20  # Rounded corner height in pixels (ST7789 physical)
```
with:
```python
SAFE_INSET = 16     # px, content margin from display edges (matches corner radius)
CORNER_RADIUS = SAFE_INSET  # Rounded corner mask radius
```

**Step 4: Update corner_mask.py**

In `device/display/corner_mask.py`, replace lines 9-10:
```python
# Corner radius matching the ST7789 display bezel
CORNER_RADIUS = 8
```
with:
```python
from display.tokens import CORNER_RADIUS
```

And update `__init__` default parameter from `radius: int = CORNER_RADIUS` — this should still work since `CORNER_RADIUS` is now imported from tokens.

**Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_safe_area.py -v`
Expected: 3 PASSED

**Step 6: Commit**

```bash
git add device/display/tokens.py device/display/corner_mask.py tests/test_safe_area.py
git commit -m "feat: add SAFE_INSET constant and unify CORNER_RADIUS to 16px"
```

---

### Task 2: Safe Area — Apply SAFE_INSET to composite screen layout

**Files:**
- Modify: `device/ui/composite_screen.py:29-30` (HINT_BAR_H, RIGHT_PANEL_H)
- Modify: `device/ui/composite_screen.py:67-85` (render method)
- Test: `tests/test_composite_screen.py` (existing — verify nothing breaks)

**Context:** The composite screen currently renders status bar at y=0 and hint bar at y=268. With SAFE_INSET=16, the status bar should start at y=16 and the bottom bar should end at y=264 (280-16). The sidebar and right panel adjust accordingly.

**Step 1: Update composite_screen.py layout constants**

In `device/ui/composite_screen.py`, add the import and update constants:

```python
from device.display.tokens import PHYSICAL_W, PHYSICAL_H, SIDEBAR_W, CONTENT_W, STATUS_BAR_H, SAFE_INSET
```

Replace the layout constants:
```python
HINT_BAR_H = 12
RIGHT_PANEL_H = PHYSICAL_H - STATUS_BAR_H - HINT_BAR_H  # 250
```
with:
```python
HINT_BAR_H = 20  # Upgraded action bar height
CONTENT_TOP = SAFE_INSET + STATUS_BAR_H  # 36 (16 + 20)
CONTENT_BOTTOM = PHYSICAL_H - SAFE_INSET - HINT_BAR_H  # 244 (280 - 16 - 20)
RIGHT_PANEL_H = CONTENT_BOTTOM - CONTENT_TOP  # 208
```

**Step 2: Update render method**

Update the render method to use safe-area-aware positions:

```python
def render(self, surface: pygame.Surface) -> None:
    surface.fill(BLACK)

    # Status bar at top (within safe area)
    self._status_bar.render(surface, y=SAFE_INSET, width=PHYSICAL_W)

    # Sidebar on left (from below status bar to above action bar)
    self._sidebar.render(surface, x=0, y=CONTENT_TOP, height=RIGHT_PANEL_H)

    # Right panel
    label = self._sidebar.items[self._sidebar.selected_index]
    panel = self._right_panels.get(label)
    if panel is not None:
        self._right_surface.fill(BLACK)
        panel.render(self._right_surface)
        surface.blit(self._right_surface, (SIDEBAR_W, CONTENT_TOP))

    # Action bar at bottom (within safe area)
    self._hint_bar.render(surface, y=CONTENT_BOTTOM, width=PHYSICAL_W)
```

**Step 3: Update right surface size**

In `__init__`, update the right surface allocation:
```python
self._right_surface = pygame.Surface((CONTENT_W, RIGHT_PANEL_H))
```

**Step 4: Run existing tests**

Run: `python3 -m pytest tests/test_composite_screen.py -v`
Expected: All 20 tests PASS (tests check behavior, not pixel positions)

**Step 5: Commit**

```bash
git add device/ui/composite_screen.py
git commit -m "feat: apply SAFE_INSET to composite screen layout"
```

---

### Task 3: Safe Area — Apply SAFE_INSET to chat panel layout

**Files:**
- Modify: `device/screens/panels/chat.py:12-22` (imports)
- Modify: `device/screens/panels/chat.py:212-302` (render method)
- Test: `tests/test_chat_panel.py` (existing — verify nothing breaks)

**Context:** The chat panel is full-screen (240x280). It needs to respect SAFE_INSET on all four edges: status bar pushed down 16px, action menu pushed up 16px, message text inset 16px from left/right.

**Step 1: Add SAFE_INSET import**

In `device/screens/panels/chat.py`, add `SAFE_INSET` to the tokens import:
```python
from display.tokens import (
    BLACK, WHITE, DIM1, DIM2, DIM3, HAIRLINE,
    PHYSICAL_W, PHYSICAL_H, STATUS_BAR_H, SAFE_INSET,
)
```

**Step 2: Update layout constants**

Update the class-level constants:
```python
_ACTION_ROW_H = 18
_HINT_H = 20  # Upgraded action bar height (was 12)
```

**Step 3: Update render method positions**

In the `render()` method, update all positions to use safe area:

Status bar section — shift down by SAFE_INSET:
```python
status_y = SAFE_INSET
pygame.draw.line(surface, HAIRLINE, (0, status_y + STATUS_BAR_H - 1), (PHYSICAL_W, status_y + STATUS_BAR_H - 1))
header_text = self._font_small.render("CHAT", False, WHITE)
surface.blit(header_text, (SAFE_INSET, status_y + (STATUS_BAR_H - header_text.get_height()) // 2))
```

Message area — use safe insets:
```python
msg_area_top = status_y + STATUS_BAR_H + 2
msg_area_bottom = PHYSICAL_H - SAFE_INSET - action_menu_h - hint_h - 2
```

Message text rendering — inset from left:
```python
visible_lines = []
for msg in snapshot:
    prefix = "> " if msg["role"] == "user" else ""
    color = DIM2 if msg["role"] == "user" else WHITE
    lines = self._wrap_text(prefix + msg["text"], PHYSICAL_W - SAFE_INSET * 2)
    for line in lines:
        visible_lines.append((line, color))
```

Text blitting — use SAFE_INSET for x position:
```python
text_surface = self._font.render(line_text, False, color)
surface.blit(text_surface, (SAFE_INSET, msg_y))
```

Action menu — shift up by SAFE_INSET:
```python
action_top = PHYSICAL_H - SAFE_INSET - action_menu_h - hint_h
```

Action menu rows — inset from left:
```python
row_surface = self._font.render(prefix + label, False, text_color)
surface.blit(row_surface, (SAFE_INSET, y + 1))
```

Hint bar — position within safe area:
```python
hint_y = PHYSICAL_H - SAFE_INSET - hint_h
```

**Step 4: Run existing tests**

Run: `python3 -m pytest tests/test_chat_panel.py -v`
Expected: 7 passed, 1 skipped

**Step 5: Commit**

```bash
git add device/screens/panels/chat.py
git commit -m "feat: apply SAFE_INSET to chat panel layout"
```

---

### Task 4: Action Bar — Replace HintBar with ActionBar

**Files:**
- Create: `device/ui/components/action_bar.py`
- Modify: `device/ui/composite_screen.py` (import ActionBar instead of HintBar)
- Modify: `device/screens/panels/chat.py` (use ActionBar API for per-mode hints)
- Test: `tests/test_action_bar.py`

**Context:** The HintBar is 12px/8pt text-only. The new ActionBar is 20px/10pt with gesture icons (circle outline for tap, double circle for double-tap, filled circle for hold). Each screen sets actions as `(icon_type, label)` tuples.

**Step 1: Write the failing test**

Create `tests/test_action_bar.py`:

```python
"""Tests for ActionBar component."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from ui.components.action_bar import ActionBar


class ActionBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_default_actions(self):
        bar = ActionBar()
        self.assertEqual(len(bar.actions), 3)

    def test_set_actions(self):
        bar = ActionBar()
        bar.set_actions([("tap", "SEND"), ("hold", "CANCEL")])
        self.assertEqual(len(bar.actions), 2)
        self.assertEqual(bar.actions[0], ("tap", "SEND"))

    def test_set_text_fallback(self):
        bar = ActionBar()
        bar.set_text("listening...")
        self.assertEqual(bar.text, "listening...")
        self.assertEqual(len(bar.actions), 0)

    def test_icon_types_valid(self):
        bar = ActionBar()
        bar.set_actions([("tap", "A"), ("double", "B"), ("hold", "C")])
        for icon_type, _ in bar.actions:
            self.assertIn(icon_type, ("tap", "double", "hold"))


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_action_bar.py -v`
Expected: FAIL — `action_bar` module doesn't exist.

**Step 3: Create ActionBar**

Create `device/ui/components/action_bar.py`:

```python
"""ActionBar component — bottom gesture hints with icons.

Replaces the old HintBar. Shows gesture icons + labels, 20px tall.
Each screen/mode sets actions as (icon_type, label) tuples.
"""

import pygame

from display.tokens import DIM2, DIM3, HAIRLINE, PHYSICAL_W

ACTION_BAR_H = 20
FONT_SIZE = 10
PAD_Y = 4

# Default actions for most screens
DEFAULT_ACTIONS = [
    ("tap", "NEXT"),
    ("double", "SELECT"),
    ("hold", "BACK"),
]


class ActionBar:
    """Renders the bottom action bar with gesture icons."""

    def __init__(self):
        self.actions: list[tuple[str, str]] = list(DEFAULT_ACTIONS)
        self.text: str = ""  # Fallback plain text mode

    def set_actions(self, actions: list[tuple[str, str]]) -> None:
        """Set action items as (icon_type, label) tuples.

        icon_type: 'tap' (circle outline), 'double' (double circle), 'hold' (filled circle)
        """
        self.actions = list(actions)
        self.text = ""

    def set_text(self, text: str) -> None:
        """Set plain text mode (no icons). Used for states like 'listening...'"""
        self.text = text
        self.actions = []

    def render(self, surface: pygame.Surface, y: int, width: int = PHYSICAL_W) -> None:
        """Draw action bar at y position across full width."""
        from display.theme import load_ui_font

        font = load_ui_font("small", {})

        # Top separator
        pygame.draw.line(surface, HAIRLINE, (0, y), (width, y))

        center_y = y + ACTION_BAR_H // 2

        # Plain text mode
        if self.text:
            text_surf = font.render(self.text, False, DIM3)
            surface.blit(text_surf, ((width - text_surf.get_width()) // 2, center_y - text_surf.get_height() // 2))
            return

        if not self.actions:
            return

        # Calculate total width for even spacing
        items = []
        for icon_type, label in self.actions:
            label_surf = font.render(label, False, DIM2)
            items.append((icon_type, label_surf))

        total_width = sum(8 + 4 + s.get_width() for _, s in items)  # icon(8) + gap(4) + label
        spacing = (width - total_width) // (len(items) + 1)
        x = spacing

        for icon_type, label_surf in items:
            # Draw gesture icon (6px diameter circle)
            icon_center = (x + 4, center_y)
            if icon_type == "tap":
                pygame.draw.circle(surface, DIM2, icon_center, 3, 1)  # outline
            elif icon_type == "double":
                pygame.draw.circle(surface, DIM2, icon_center, 3, 1)  # outer
                pygame.draw.circle(surface, DIM2, icon_center, 1, 1)  # inner dot
            elif icon_type == "hold":
                pygame.draw.circle(surface, DIM2, icon_center, 3, 0)  # filled

            # Draw label
            surface.blit(label_surf, (x + 8 + 4, center_y - label_surf.get_height() // 2))
            x += 8 + 4 + label_surf.get_width() + spacing
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_action_bar.py -v`
Expected: 4 PASSED

**Step 5: Wire ActionBar into CompositeScreen**

In `device/ui/composite_screen.py`, replace:
```python
from device.ui.components.hint_bar import HintBar
```
with:
```python
from device.ui.components.action_bar import ActionBar
```

Replace `HintBar()` with `ActionBar()` in `__init__`. The `render()` call stays the same signature: `self._hint_bar.render(surface, y=..., width=...)`. Rename `_hint_bar` to `_action_bar` throughout the class.

Update `get_hint()` to return text from action bar.

**Step 6: Run composite screen tests**

Run: `python3 -m pytest tests/test_composite_screen.py -v`
Expected: All 20 PASS

**Step 7: Commit**

```bash
git add device/ui/components/action_bar.py tests/test_action_bar.py device/ui/composite_screen.py
git commit -m "feat: replace HintBar with ActionBar — gesture icons + 20px height"
```

---

### Task 5: Chat State Machine — Input mode enum and dispatch

**Files:**
- Modify: `device/screens/panels/chat.py` (major rework of handle_action + new ChatMode enum)
- Test: `tests/test_chat_panel.py` (rewrite for new mode-based behavior)

**Context:** This is the core change. Replace the SPEAK/ACTIONS/BACK action menu with a `ChatMode` enum that gates all input handling. The chat panel's `handle_action()` dispatches to mode-specific handlers.

**Step 1: Write the failing tests**

Rewrite `tests/test_chat_panel.py`:

```python
"""Tests for ChatPanel gesture-driven input modes."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.chat import ChatPanel, ChatMode


class ChatModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_panel(self, **kwargs):
        client = MagicMock()
        client.chat = MagicMock(return_value=iter(["hello"]))
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=None)
        repo.get_latest_session = MagicMock(return_value=None)
        audio = kwargs.get("audio", MagicMock())
        audio.is_speaking = MagicMock(return_value=False)
        audio.is_available = MagicMock(return_value=True)
        return ChatPanel(
            client=client,
            repository=repo,
            on_back=kwargs.get("on_back"),
            audio_pipeline=audio,
        )

    def test_starts_in_idle_mode(self):
        panel = self._make_panel()
        self.assertEqual(panel._mode, ChatMode.IDLE)

    def test_long_press_in_idle_exits_chat(self):
        called = []
        panel = self._make_panel(on_back=lambda: called.append(True))
        panel.handle_action("LONG_PRESS")
        self.assertTrue(called)

    def test_double_press_in_idle_opens_actions(self):
        panel = self._make_panel()
        panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel._mode, ChatMode.ACTIONS)

    def test_short_press_in_actions_cycles(self):
        panel = self._make_panel()
        panel._mode = ChatMode.ACTIONS
        panel._action_template_index = 0
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._action_template_index, 1)

    def test_long_press_in_actions_returns_to_idle(self):
        panel = self._make_panel()
        panel._mode = ChatMode.ACTIONS
        panel.handle_action("LONG_PRESS")
        self.assertEqual(panel._mode, ChatMode.IDLE)

    def test_long_press_in_recording_cancels(self):
        panel = self._make_panel()
        panel._mode = ChatMode.RECORDING
        panel.handle_action("LONG_PRESS")
        self.assertEqual(panel._mode, ChatMode.IDLE)

    def test_short_press_in_recording_sends(self):
        panel = self._make_panel()
        panel._mode = ChatMode.RECORDING
        # SHORT in recording triggers send (sets stop event)
        panel.handle_action("SHORT_PRESS")
        self.assertTrue(panel._voice_stop_event.is_set())

    def test_short_press_in_idle_scrolls(self):
        panel = self._make_panel()
        panel._scroll_offset = 5
        panel.handle_action("SHORT_PRESS")
        # Should scroll (decrease offset toward 0)
        self.assertEqual(panel._scroll_offset, 4)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_chat_panel.py -v`
Expected: FAIL — `ChatMode` doesn't exist yet.

**Step 3: Implement ChatMode and refactored handle_action**

In `device/screens/panels/chat.py`, add the enum after imports:

```python
from enum import Enum, auto
import threading

class ChatMode(Enum):
    IDLE = auto()       # Viewing chat history
    RECORDING = auto()  # Capturing audio
    ACTIONS = auto()    # Quick actions menu
    STREAMING = auto()  # Response arriving
    SPEAKING = auto()   # TTS playing
```

Replace the state variables in `__init__`:

Remove:
```python
self._voice_stop_requested = False
self._action_index = 0
self._showing_actions = False
```

Add:
```python
self._mode = ChatMode.IDLE
self._voice_stop_event = threading.Event()
self._hold_timer: float | None = None  # For hold-to-record
```

Keep `_action_template_index` for the ACTIONS sub-menu.

Replace `handle_action` entirely:

```python
def handle_action(self, action: str):
    # Dispatch to mode-specific handler
    handler = {
        ChatMode.IDLE: self._handle_idle,
        ChatMode.RECORDING: self._handle_recording,
        ChatMode.ACTIONS: self._handle_actions,
        ChatMode.STREAMING: self._handle_streaming,
        ChatMode.SPEAKING: self._handle_speaking,
    }.get(self._mode)
    if handler:
        handler(action)

def _handle_idle(self, action: str):
    if action == "SHORT_PRESS":
        # Scroll messages up
        self._scroll_offset = max(0, self._scroll_offset - 1)
    elif action == "TRIPLE_PRESS":
        # Scroll messages down
        self._scroll_offset += 1
    elif action == "DOUBLE_PRESS":
        # Open quick actions
        self._mode = ChatMode.ACTIONS
        self._action_template_index = 0
    elif action == "LONG_PRESS":
        # Exit chat
        if self._on_back:
            self._on_back()

def _handle_recording(self, action: str):
    if action in ("SHORT_PRESS", "DOUBLE_PRESS"):
        # Send recording
        self._voice_stop_event.set()
    elif action == "LONG_PRESS":
        # Cancel recording
        self._voice_stop_event.set()
        self._recording_cancelled = True
        self._mode = ChatMode.IDLE

def _handle_actions(self, action: str):
    items = list(self._templates) + [{"label": "BACK", "message": ""}]
    if action == "SHORT_PRESS":
        self._action_template_index = (self._action_template_index + 1) % len(items)
    elif action == "TRIPLE_PRESS":
        self._action_template_index = (self._action_template_index - 1) % len(items)
    elif action == "DOUBLE_PRESS":
        selected = items[self._action_template_index]
        if selected["label"] == "BACK":
            self._mode = ChatMode.IDLE
        else:
            self._send_template_message(selected)
            self._mode = ChatMode.IDLE
    elif action == "LONG_PRESS":
        self._mode = ChatMode.IDLE

def _handle_streaming(self, action: str):
    pass  # Ignore all input while streaming

def _handle_speaking(self, action: str):
    if action in ("SHORT_PRESS", "DOUBLE_PRESS", "LONG_PRESS"):
        if self._audio_pipeline:
            self._audio_pipeline.stop_speaking()
        self._mode = ChatMode.IDLE
```

**Step 4: Wire HOLD_START for recording**

In `main.py`, add HOLD_START/HOLD_END forwarding to the screen manager:

```python
button.on(ButtonEvent.HOLD_START, lambda: _on_button(ButtonEvent.HOLD_START))
button.on(ButtonEvent.HOLD_END, lambda: _on_button(ButtonEvent.HOLD_END))
```

In `ChatPanel`, handle HOLD_START:
```python
def handle_action(self, action: str):
    if action == "HOLD_START" and self._mode == ChatMode.IDLE:
        self._hold_timer = time.time()
        return
    if action == "HOLD_END" and self._hold_timer is not None:
        elapsed = time.time() - self._hold_timer
        self._hold_timer = None
        if elapsed >= 0.4 and self._mode == ChatMode.RECORDING:
            return  # Already recording, hold release is a no-op
        return
    # ... rest of dispatch
```

In the `update()` method, check hold timer to start recording:
```python
def update(self, dt: float):
    self._cursor_anim.update(dt)
    # Check if hold has crossed the recording threshold
    if self._hold_timer is not None and self._mode == ChatMode.IDLE:
        elapsed = time.time() - self._hold_timer
        if elapsed >= 0.4:
            self._hold_timer = None
            self._start_recording()
```

**Step 5: Refactor _capture_voice_input to use threading.Event**

Rename `_capture_voice_input` → `_start_recording`, replace boolean flag with Event:

```python
def _start_recording(self):
    if self._mode == ChatMode.RECORDING or not self._audio_pipeline:
        return
    self._mode = ChatMode.RECORDING
    self._recording_cancelled = False
    self._voice_stop_event.clear()
    self._recording_start_time = time.time()
    if self._led:
        self._led.listening()
    threading.Thread(target=self._do_voice_capture, daemon=True).start()
```

Update `_do_voice_capture` to use the Event:
```python
def _do_voice_capture(self):
    try:
        audio_path = self._audio_pipeline.record(max_seconds=30)
        if not audio_path:
            self._mode = ChatMode.IDLE
            if self._led:
                self._led.off()
            return
        # Wait for stop event (set by button press)
        self._voice_stop_event.wait(timeout=30)
        self._audio_pipeline.stop_recording()

        if self._recording_cancelled:
            self._mode = ChatMode.IDLE
            if self._led:
                self._led.off()
            return

        self._mode = ChatMode.STREAMING
        with self._messages_lock:
            self._status_detail = "transcribing..."
        text = self._audio_pipeline.transcribe(audio_path).strip()
    except Exception as exc:
        self._mode = ChatMode.IDLE
        if self._led:
            self._led.error()
        self._status_detail = f"voice err: {str(exc)[:20]}"
        return

    if self._led:
        self._led.off()
    if not text:
        with self._messages_lock:
            self._status_detail = "Didn't catch that"
        self._mode = ChatMode.IDLE
        return
    self._input_text = text
    self._send_message()
```

**Step 6: Update render method for mode-aware action bar**

In the render method, replace the action menu section with mode-aware rendering.

For IDLE mode: show recent messages, no action menu overlay.
For RECORDING mode: show `●REC` + elapsed time + volume bar.
For ACTIONS mode: show template list overlay.
For STREAMING/SPEAKING: show response with typewriter (Task 7).

Update the hint bar text per mode:
```python
if self._mode == ChatMode.RECORDING:
    # Will be replaced by ActionBar API in integration step
    hint_text = "TAP:SEND · LONG:CANCEL"
elif self._mode == ChatMode.ACTIONS:
    hint_text = "SHORT:NEXT · DBL:SEL · LONG:BACK"
elif self._mode == ChatMode.SPEAKING:
    hint_text = "TAP:STOP"
elif self._mode == ChatMode.STREAMING:
    hint_text = "listening..."
else:
    hint_text = "HOLD:RECORD · DBL:ACTIONS · LONG:BACK"
```

**Step 7: Run tests**

Run: `python3 -m pytest tests/test_chat_panel.py -v`
Expected: 8 PASSED

**Step 8: Commit**

```bash
git add device/screens/panels/chat.py tests/test_chat_panel.py device/main.py
git commit -m "feat: chat input state machine — gesture-driven modes with hold-to-record"
```

---

### Task 6: Chat State Machine — Wire ActionBar into chat modes

**Files:**
- Modify: `device/screens/panels/chat.py` (use ActionBar for per-mode hints)
- Test: `tests/test_chat_panel.py` (add action bar state tests)

**Context:** Now that both ActionBar and ChatMode exist, wire them together so each mode sets the appropriate action bar content.

**Step 1: Add action bar state tests**

Add to `tests/test_chat_panel.py`:

```python
def test_idle_mode_action_bar(self):
    panel = self._make_panel()
    self.assertEqual(panel._mode, ChatMode.IDLE)
    bar_actions = panel._get_action_bar_content()
    self.assertEqual(len(bar_actions), 3)
    icons = [a[0] for a in bar_actions]
    self.assertIn("hold", icons)

def test_recording_mode_action_bar(self):
    panel = self._make_panel()
    panel._mode = ChatMode.RECORDING
    bar_actions = panel._get_action_bar_content()
    self.assertEqual(len(bar_actions), 2)

def test_actions_mode_action_bar(self):
    panel = self._make_panel()
    panel._mode = ChatMode.ACTIONS
    bar_actions = panel._get_action_bar_content()
    icons = [a[0] for a in bar_actions]
    self.assertIn("double", icons)
```

**Step 2: Add `_get_action_bar_content()` method to ChatPanel**

```python
def _get_action_bar_content(self) -> list[tuple[str, str]]:
    """Return action bar items for the current mode."""
    if self._mode == ChatMode.IDLE:
        return [("hold", "RECORD"), ("double", "ACTIONS"), ("tap", "SCROLL")]
    elif self._mode == ChatMode.RECORDING:
        return [("tap", "SEND"), ("hold", "CANCEL")]
    elif self._mode == ChatMode.ACTIONS:
        return [("tap", "NEXT"), ("double", "SELECT"), ("hold", "BACK")]
    elif self._mode == ChatMode.SPEAKING:
        return [("tap", "STOP")]
    return []  # STREAMING — show text "listening..." instead
```

**Step 3: Use in render method**

In the render method's hint bar section, replace the hint text logic:

```python
# ── Action bar ──
hint_y = PHYSICAL_H - SAFE_INSET - self._HINT_H
bar_content = self._get_action_bar_content()
if bar_content:
    # Render action items with icons
    total_items = len(bar_content)
    item_spacing = PHYSICAL_W // (total_items + 1)
    for i, (icon_type, label) in enumerate(bar_content):
        x = item_spacing * (i + 1)
        center_y = hint_y + self._HINT_H // 2
        # Draw icon
        if icon_type == "tap":
            pygame.draw.circle(surface, DIM2, (x - 20, center_y), 3, 1)
        elif icon_type == "double":
            pygame.draw.circle(surface, DIM2, (x - 20, center_y), 3, 1)
            pygame.draw.circle(surface, DIM2, (x - 20, center_y), 1, 1)
        elif icon_type == "hold":
            pygame.draw.circle(surface, DIM2, (x - 20, center_y), 3, 0)
        # Draw label
        label_surf = self._font_small.render(label, False, DIM2)
        surface.blit(label_surf, (x - 14, center_y - label_surf.get_height() // 2))
else:
    # Plain text mode (STREAMING)
    hint = self._font_small.render("listening...", False, DIM3)
    surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, hint_y + 4))
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_chat_panel.py -v`
Expected: 11 PASSED

**Step 5: Commit**

```bash
git add device/screens/panels/chat.py tests/test_chat_panel.py
git commit -m "feat: wire ActionBar content to chat input modes"
```

---

### Task 7: Typewriter Renderer

**Files:**
- Create: `device/display/typewriter.py`
- Test: `tests/test_typewriter.py`

**Context:** Response text should reveal word-by-word with punctuation-aware pauses. The renderer buffers full text and exposes `get_visible_text()` for the chat panel to call each frame.

**Step 1: Write the failing tests**

Create `tests/test_typewriter.py`:

```python
"""Tests for TypewriterRenderer."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from display.typewriter import TypewriterRenderer, SPEED_PRESETS


class TypewriterTests(unittest.TestCase):
    def test_instant_reveals_all(self):
        tw = TypewriterRenderer("Hello world", speed="instant")
        tw.update(0.01)
        self.assertEqual(tw.get_visible_text(), "Hello world")

    def test_empty_text(self):
        tw = TypewriterRenderer("", speed="normal")
        tw.update(1.0)
        self.assertEqual(tw.get_visible_text(), "")

    def test_progressive_reveal(self):
        tw = TypewriterRenderer("one two three", speed="normal")
        # At 3 words/sec, first word at ~0.33s
        tw.update(0.0)
        self.assertEqual(tw.get_visible_text(), "")
        tw.update(0.35)
        visible = tw.get_visible_text()
        self.assertIn("one", visible)
        self.assertNotIn("three", visible)

    def test_finished_property(self):
        tw = TypewriterRenderer("Hi", speed="instant")
        self.assertFalse(tw.finished)
        tw.update(0.01)
        self.assertTrue(tw.finished)

    def test_period_adds_pause(self):
        tw = TypewriterRenderer("End. Start", speed="fast")
        # At 6 words/sec (~0.167s/word), period adds 0.4s
        tw.update(0.2)  # First word revealed
        visible_after_first = tw.get_visible_text()
        self.assertIn("End.", visible_after_first)
        tw.update(0.1)  # Still in pause
        self.assertNotIn("Start", tw.get_visible_text())
        tw.update(0.4)  # Past pause
        self.assertIn("Start", tw.get_visible_text())

    def test_speed_presets_exist(self):
        for preset in ("slow", "normal", "fast", "instant"):
            self.assertIn(preset, SPEED_PRESETS)

    def test_reset(self):
        tw = TypewriterRenderer("Hello world", speed="instant")
        tw.update(1.0)
        self.assertTrue(tw.finished)
        tw.reset("New text")
        self.assertFalse(tw.finished)
        self.assertEqual(tw.get_visible_text(), "")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_typewriter.py -v`
Expected: FAIL — module doesn't exist.

**Step 3: Implement TypewriterRenderer**

Create `device/display/typewriter.py`:

```python
"""TypewriterRenderer — progressive word-by-word text reveal.

Reveals response text at a configurable speed with punctuation-aware pauses.
Call update(dt) each frame, then get_visible_text() for the current state.
"""

from __future__ import annotations

import re

# Words per second for each preset
SPEED_PRESETS: dict[str, float] = {
    "slow": 2.0,
    "normal": 3.0,
    "fast": 6.0,
    "instant": float("inf"),
}

# Extra pause (seconds) after punctuation
PAUSE_PERIOD = 0.4      # . ? !
PAUSE_COMMA = 0.15       # , : ;
PAUSE_PARAGRAPH = 0.6    # \n\n


class TypewriterRenderer:
    """Progressive word-by-word text reveal with punctuation pauses."""

    def __init__(self, text: str, speed: str = "normal"):
        self._words: list[str] = []
        self._pauses: list[float] = []  # Extra pause after each word
        self._words_per_sec = SPEED_PRESETS.get(speed, SPEED_PRESETS["normal"])
        self._revealed_count = 0
        self._elapsed = 0.0
        self._next_reveal_at = 0.0
        self._finished = False

        self._parse(text)

    def _parse(self, text: str) -> None:
        """Split text into words and calculate per-word pause times."""
        if not text:
            self._finished = True
            return

        # Split keeping whitespace attached to preceding word
        raw_words = text.split(" ")
        self._words = []
        self._pauses = []

        for w in raw_words:
            if not w:
                continue
            self._words.append(w)

            # Calculate extra pause based on trailing punctuation
            pause = 0.0
            if w.endswith(("\n\n",)):
                pause = PAUSE_PARAGRAPH
            elif w.rstrip().endswith((".", "?", "!")):
                pause = PAUSE_PERIOD
            elif w.rstrip().endswith((",", ":", ";")):
                pause = PAUSE_COMMA
            self._pauses.append(pause)

        if self._words_per_sec == float("inf"):
            self._revealed_count = len(self._words)
            self._finished = True

    def update(self, dt: float) -> None:
        """Advance the typewriter by dt seconds."""
        if self._finished or not self._words:
            return

        self._elapsed += dt

        while self._revealed_count < len(self._words) and self._elapsed >= self._next_reveal_at:
            self._revealed_count += 1
            if self._revealed_count < len(self._words):
                word_interval = 1.0 / self._words_per_sec
                extra_pause = self._pauses[self._revealed_count - 1]
                self._next_reveal_at += word_interval + extra_pause

        if self._revealed_count >= len(self._words):
            self._finished = True

    def get_visible_text(self) -> str:
        """Return the currently revealed portion of text."""
        if not self._words:
            return ""
        return " ".join(self._words[:self._revealed_count])

    @property
    def finished(self) -> bool:
        return self._finished

    def reset(self, text: str, speed: str | None = None) -> None:
        """Reset with new text."""
        if speed:
            self._words_per_sec = SPEED_PRESETS.get(speed, SPEED_PRESETS["normal"])
        self._revealed_count = 0
        self._elapsed = 0.0
        self._next_reveal_at = 0.0
        self._finished = False
        self._words = []
        self._pauses = []
        self._parse(text)
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_typewriter.py -v`
Expected: 7 PASSED

**Step 5: Commit**

```bash
git add device/display/typewriter.py tests/test_typewriter.py
git commit -m "feat: TypewriterRenderer — word-by-word reveal with punctuation pauses"
```

---

### Task 8: Typewriter — Integrate into chat panel

**Files:**
- Modify: `device/screens/panels/chat.py` (use TypewriterRenderer for response display)
- Test: `tests/test_chat_panel.py` (add typewriter integration tests)

**Context:** When a response arrives (via `_stream_response`), instead of showing the full text immediately, feed it to a TypewriterRenderer. The render method shows `typewriter.get_visible_text()` for the latest assistant message.

**Step 1: Add TypewriterRenderer to ChatPanel**

In `__init__`, add:
```python
from display.typewriter import TypewriterRenderer
self._typewriter: TypewriterRenderer | None = None
```

**Step 2: Feed response text to typewriter**

In `_stream_response`, after the response is complete:
```python
# After full response text is assembled
speed = "normal"
if self._repository:
    speed = str(self._repository.get_setting("text_speed", "normal"))
self._typewriter = TypewriterRenderer(response_text, speed=speed)
self._mode = ChatMode.STREAMING
```

During SSE streaming, accumulate text but don't show it yet (the typewriter reveals it progressively):
```python
# In the streaming loop, update the messages deque with full text as before
# but the render method checks _typewriter for display
```

**Step 3: Update update() to tick typewriter**

```python
def update(self, dt: float):
    self._cursor_anim.update(dt)
    if self._typewriter and not self._typewriter.finished:
        self._typewriter.update(dt)
    elif self._typewriter and self._typewriter.finished:
        # Typewriter done — move to SPEAKING or IDLE
        if self._audio_pipeline and self._is_streaming:
            pass  # TTS will handle mode transition
        elif self._mode == ChatMode.STREAMING:
            self._mode = ChatMode.IDLE
            self._typewriter = None
    # Hold timer check...
```

**Step 4: Update render to use typewriter for latest message**

In the messages rendering section, check if typewriter is active:
```python
# If typewriter is active, override the last assistant message's visible text
if self._typewriter and snapshot and snapshot[-1]["role"] == "assistant":
    snapshot[-1] = {"role": "assistant", "text": self._typewriter.get_visible_text()}
```

**Step 5: Run tests**

Run: `python3 -m pytest tests/test_chat_panel.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add device/screens/panels/chat.py tests/test_chat_panel.py
git commit -m "feat: integrate TypewriterRenderer into chat panel response display"
```

---

### Task 9: Text Speed Setting — Add TextSpeedPanel to settings

**Files:**
- Modify: `device/screens/panels/settings.py` (add TextSpeedPanel + nav item)
- Modify: `device/main.py` (wire open_text_speed)
- Test: existing settings wiring test patterns

**Context:** Users need to pick text speed (SLOW/NORMAL/FAST/INSTANT) from settings.

**Step 1: Add TextSpeedPanel to settings.py**

Add after FontPickerPanel:

```python
class TextSpeedPanel(BaseScreen):
    """Pick typewriter text reveal speed."""
    _owns_status_bar = True

    OPTIONS = [
        ("slow", "SLOW"),
        ("normal", "NORMAL"),
        ("fast", "FAST"),
        ("instant", "INSTANT"),
    ]

    def __init__(self, repository: DeviceRepository, on_back=None, ui_settings=None):
        self._repo = repository
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        current = str(self._repo.get_setting("text_speed", "normal"))
        self._selected = next((i for i, (v, _) in enumerate(self.OPTIONS) if v == current), 1)

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._selected = (self._selected + 1) % len(self.OPTIONS)
        elif action == "TRIPLE_PRESS":
            self._selected = (self._selected - 1) % len(self.OPTIONS)
        elif action == "DOUBLE_PRESS":
            value, _ = self.OPTIONS[self._selected]
            self._repo.set_setting("text_speed", value)
            if self._on_back:
                self._on_back()
        elif action == "LONG_PRESS":
            if self._on_back:
                self._on_back()

    def render(self, surface: pygame.Surface):
        from display.tokens import SAFE_INSET
        surface.fill(BLACK)
        header = self._font_small.render("TEXT SPEED", False, WHITE)
        surface.blit(header, (SAFE_INSET, SAFE_INSET + 2))
        y = SAFE_INSET + STATUS_BAR_H + 4
        for i, (value, label) in enumerate(self.OPTIONS):
            focused = i == self._selected
            prefix = "> " if focused else "- "
            color = WHITE if focused else DIM2
            text = self._font.render(prefix + label, False, color)
            surface.blit(text, (SAFE_INSET, y))
            y += ROW_H_MIN
```

**Step 2: Add nav item in SettingsPanel**

Add "TEXT SPEED" to the settings nav items list, with status showing current value. Wire `on_open_text_speed` callback.

**Step 3: Wire in main.py**

Add `open_text_speed` function and pass to SettingsPanel:
```python
def open_text_speed():
    screen_mgr.push(TextSpeedPanel(repository=repository, on_back=lambda: screen_mgr.pop(), ui_settings=ui_settings))
```

Add `on_open_text_speed=open_text_speed` to the SettingsPanel constructor call.

**Step 4: Import TextSpeedPanel in main.py**

Add to the settings import line:
```python
from screens.panels.settings import SettingsPanel, ModelPickerPanel, AgentModePanel, SleepTimerPanel, AboutPanel, BatteryPanel, DevPanel, FontPickerPanel, TextSpeedPanel
```

**Step 5: Run tests**

Run: `python3 -m pytest tests/test_settings_wiring.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add device/screens/panels/settings.py device/main.py
git commit -m "feat: TextSpeedPanel — configurable typewriter speed in settings"
```

---

### Task 10: HOLD_START/HOLD_END — Wire button events through main.py

**Files:**
- Modify: `device/main.py:233-236` (add HOLD_START/HOLD_END callbacks)
- Modify: `device/screens/manager.py` (forward HOLD events to current screen)
- Test: Manually test on device

**Context:** HOLD_START and HOLD_END events exist in ButtonHandler but aren't forwarded to screens. Chat's hold-to-record needs them.

**Step 1: Add HOLD event forwarding in main.py**

After line 236, add:
```python
button.on(ButtonEvent.HOLD_START, lambda: _on_button(ButtonEvent.HOLD_START))
button.on(ButtonEvent.HOLD_END, lambda: _on_button(ButtonEvent.HOLD_END))
```

**Step 2: Update ScreenManager.handle_action**

In `device/screens/manager.py`, ensure `handle_action` passes HOLD_START/HOLD_END to the current screen's `handle_action`. Check that the screen manager doesn't filter out unknown action names.

**Step 3: Run all tests**

Run: `python3 -m pytest tests/ -v --ignore=tests/test_mail_panel.py --ignore=tests/test_messages_panel.py`
Expected: All PASS

**Step 4: Commit**

```bash
git add device/main.py device/screens/manager.py
git commit -m "feat: forward HOLD_START/HOLD_END button events to screen manager"
```

---

### Task 11: Flicker Investigation — Backlight and rendering checks

**Files:**
- Modify: `device/display/driver.py` (check double buffering, flip vs update)
- Modify: `device/hardware/whisplay_board.py` (check backlight control)
- No test file (investigation task)

**Context:** User reports screen flickering. Likely causes: backlight PWM instability, full redraw without double buffering, or SPI timing issues at low battery.

**Step 1: Check display driver**

Read `device/display/driver.py` and check:
- Is it using `pygame.display.flip()` or `pygame.display.update()`?
- Is double buffering enabled (`pygame.DOUBLEBUF` flag)?
- For SPI displays (fbcp/fbdev), check if vsync is used

**Step 2: Check whisplay board backlight**

Read `device/hardware/whisplay_board.py` and check:
- Is there a backlight pin? (Common: GPIO 18 or 13 for PWM)
- Is PWM being used? If so, check frequency
- Add stable backlight method if not present

**Step 3: Add DOUBLEBUF flag if missing**

In the display driver's pygame.display.set_mode call, add `pygame.DOUBLEBUF`:
```python
pygame.display.set_mode((width, height), pygame.DOUBLEBUF)
```

**Step 4: Add backlight stabilization**

If WhisPlay board has backlight control, ensure it's set to 100% on boot and not cycling:
```python
def set_backlight(self, brightness: int = 100) -> None:
    """Set backlight brightness (0-100). Default 100 for stable display."""
    # Implementation depends on hardware
```

**Step 5: Commit**

```bash
git add device/display/driver.py device/hardware/whisplay_board.py
git commit -m "fix: stabilize display — DOUBLEBUF + backlight control"
```

---

### Task 12: Final integration test + push

**Files:**
- All modified files
- Test: Full test suite

**Step 1: Run full test suite**

```bash
python3 -m pytest tests/ -v --ignore=tests/test_mail_panel.py --ignore=tests/test_messages_panel.py 2>&1 | tail -40
```

Expected: All pass (skips for pygame dummy driver are OK).

**Step 2: Push**

```bash
git push origin main
```

**Step 3: Deploy on Pi**

Provide deploy command:
```bash
cd ~/bitos && git fetch origin && git reset --hard origin/main && sudo systemctl restart bitos-device
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | SAFE_INSET constant + corner mask | tokens.py, corner_mask.py |
| 2 | Apply SAFE_INSET to composite screen | composite_screen.py |
| 3 | Apply SAFE_INSET to chat panel | chat.py |
| 4 | ActionBar replaces HintBar | action_bar.py (new), composite_screen.py |
| 5 | Chat state machine (ChatMode enum) | chat.py (major rework) |
| 6 | Wire ActionBar to chat modes | chat.py |
| 7 | TypewriterRenderer | typewriter.py (new) |
| 8 | Integrate typewriter into chat | chat.py |
| 9 | TextSpeedPanel in settings | settings.py, main.py |
| 10 | Wire HOLD_START/HOLD_END events | main.py, manager.py |
| 11 | Flicker investigation | driver.py, whisplay_board.py |
| 12 | Integration test + push | all |
