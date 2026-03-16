# Inline Recording UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the RECORD menu item in ChatPreviewPanel into a stateful row that handles record → transcribe → handoff without leaving the submenu.

**Architecture:** Add a `RecState` enum to ChatPreviewPanel. Override `handle_action()` and `render()` to route gestures and draw custom content based on state. Pass `AudioPipeline` and an STT callable through the panel registry. Dynamic greeting height replaces the fixed `GREETING_H` constant.

**Tech Stack:** pygame, existing `StepAnimator`, `AudioPipeline`, `BackendClient`, `threading` for background STT.

---

### Task 1: Fix Existing Test for MAX_GREETING_CHARS

The previous fix changed `MAX_GREETING_CHARS` from 120 to 60, but the test still expects 120.

**Files:**
- Modify: `tests/test_chat_preview.py:76-80`

**Step 1: Update the test**

```python
def test_greeting_truncated_to_max(self):
    panel = ChatPreviewPanel(on_action=MagicMock())
    long_text = "x" * 200
    panel.set_greeting(long_text)
    self.assertEqual(len(panel._greeting_text), 60)
```

**Step 2: Run test to verify it passes**

Run: `cd /Users/seb/bitos && python -m pytest tests/test_chat_preview.py -v`
Expected: All 9 tests PASS

**Step 3: Commit**

```bash
git add tests/test_chat_preview.py
git commit -m "fix: update test for MAX_GREETING_CHARS 120→60"
```

---

### Task 2: Dynamic Greeting Height

Replace fixed `GREETING_H = 70` with measured height that grows with content.

**Files:**
- Modify: `device/ui/panels/chat_preview.py:19-23, 73-110`
- Test: `tests/test_chat_preview.py`

**Step 1: Write failing tests**

Add to `tests/test_chat_preview.py`:

```python
def test_greeting_height_min(self):
    """Empty greeting should use minimum height."""
    panel = ChatPreviewPanel(on_action=MagicMock())
    self.assertEqual(panel._measured_greeting_h, 40)

def test_greeting_height_grows_with_text(self):
    """Greeting with text should measure larger than minimum."""
    panel = ChatPreviewPanel(on_action=MagicMock())
    panel.set_greeting("Hello there, good morning to you")
    # After setting text, measured height should be at least MIN
    self.assertGreaterEqual(panel._measured_greeting_h, 40)

def test_greeting_height_capped(self):
    """Greeting height should not exceed maximum."""
    panel = ChatPreviewPanel(on_action=MagicMock())
    panel._measured_greeting_h = 200  # force absurd value
    panel.set_greeting("x " * 30)  # long text
    self.assertLessEqual(panel._measured_greeting_h, 100)
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/seb/bitos && python -m pytest tests/test_chat_preview.py -v -k "greeting_height"`
Expected: FAIL — `_measured_greeting_h` doesn't exist

**Step 3: Implement dynamic greeting height**

In `device/ui/panels/chat_preview.py`, replace the constants and update `__init__` and `render`:

```python
# Replace GREETING_H = 70 with:
GREETING_H_MIN = 40
GREETING_H_DEFAULT = 70
GREETING_H_MAX = 100
```

In `__init__`, add:
```python
self._measured_greeting_h: int = GREETING_H_MIN
```

In `render()`, replace the hardcoded `GREETING_H` references. After wrapping text, measure actual height:

```python
def render(self, surface: pygame.Surface) -> None:
    font = get_font(GREETING_FONT_SIZE)
    w = surface.get_width()
    line_h = font.get_height() + 2

    # Measure greeting height
    greeting_h = GREETING_H_MIN
    if self._greeting_text:
        if self._greeting_typewriter:
            visible = self._greeting_typewriter.get_visible_text()
        else:
            visible = self._greeting_text

        lines = _wrap_text(visible, font, w - GREETING_PAD_X * 2)
        content_h = GREETING_PAD_Y + len(lines) * line_h + 4
        greeting_h = max(GREETING_H_MIN, min(content_h, GREETING_H_MAX))
        self._measured_greeting_h = greeting_h

        # Render lines
        y = GREETING_PAD_Y
        for line in lines:
            if y + line_h > greeting_h - 4:
                break
            surf = font.render(line, False, DIM3)
            surface.blit(surf, (GREETING_PAD_X, y))
            y += line_h

        # Blinking cursor while typing
        if self._greeting_typewriter and not self._greeting_typewriter.finished:
            cursor_char = "_" if self._cursor_anim.step == 0 else " "
            cursor_surf = font.render(cursor_char, False, DIM2)
            if lines:
                last_line_w = font.size(lines[-1])[0]
                cy = GREETING_PAD_Y + (len(lines) - 1) * line_h
                surface.blit(cursor_surf, (GREETING_PAD_X + last_line_w, cy))
    else:
        self._measured_greeting_h = GREETING_H_MIN

    # Separator at measured height
    pygame.draw.line(surface, HAIRLINE,
                     (GREETING_PAD_X, greeting_h - 1),
                     (w - GREETING_PAD_X, greeting_h - 1))

    # Submenu items below greeting
    self._render_items(surface, y_offset=greeting_h)
```

**Step 4: Run all chat preview tests**

Run: `cd /Users/seb/bitos && python -m pytest tests/test_chat_preview.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add device/ui/panels/chat_preview.py tests/test_chat_preview.py
git commit -m "feat: dynamic greeting height (40-100px) based on content"
```

---

### Task 3: RecState Enum and State Machine Skeleton

Add the recording state enum and state tracking to ChatPreviewPanel.

**Files:**
- Modify: `device/ui/panels/chat_preview.py:1-50`
- Test: `tests/test_chat_preview.py`

**Step 1: Write failing tests**

```python
def test_initial_rec_state_is_ready(self):
    panel = ChatPreviewPanel(on_action=MagicMock())
    from device.ui.panels.chat_preview import RecState
    self.assertEqual(panel._rec_state, RecState.READY)

def test_rec_state_transitions_to_recording(self):
    panel = ChatPreviewPanel(on_action=MagicMock())
    from device.ui.panels.chat_preview import RecState
    panel._start_inline_recording()
    self.assertEqual(panel._rec_state, RecState.RECORDING)

def test_rec_state_cancel_returns_to_ready(self):
    panel = ChatPreviewPanel(on_action=MagicMock())
    from device.ui.panels.chat_preview import RecState
    panel._start_inline_recording()
    panel._cancel_inline_recording()
    self.assertEqual(panel._rec_state, RecState.READY)
```

**Step 2: Run to verify failure**

Run: `cd /Users/seb/bitos && python -m pytest tests/test_chat_preview.py -v -k "rec_state"`
Expected: FAIL — `RecState` not found

**Step 3: Implement**

Add to `device/ui/panels/chat_preview.py` after imports:

```python
import math
import time
import threading
from enum import Enum, auto

class RecState(Enum):
    READY = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    LAUNCHING = auto()
    ERROR = auto()
```

In `ChatPreviewPanel.__init__`, add:

```python
# Recording state machine
self._rec_state = RecState.READY
self._rec_start_time: float = 0.0
self._rec_elapsed: int = -1  # cached second for timer text
self._rec_error_msg: str = ""
self._cached_audio_path: str | None = None
self._transcribed_text: str | None = None

# Animation state
self._launch_anim_frame: int = 0
self._launch_anim_duration: int = 5  # frames for expansion
self._launch_start_h: int = 22  # ITEM_H from base
self._launch_target_h: int = 50
self._launch_current_h: int = 22

# Dependencies (set via set_audio_pipeline / set_stt_callable)
self._audio_pipeline = None
self._stt_callable = None  # callable(wav_path) -> str
self._led = None
```

Add methods:

```python
def set_audio_pipeline(self, pipeline, led=None):
    """Wire audio pipeline and LED for inline recording."""
    self._audio_pipeline = pipeline
    self._led = led

def set_stt_callable(self, stt_fn):
    """Set the STT function: callable(wav_path) -> str."""
    self._stt_callable = stt_fn

def _start_inline_recording(self):
    self._rec_state = RecState.RECORDING
    self._rec_start_time = time.time()
    self._rec_elapsed = -1
    if self._audio_pipeline:
        self._audio_pipeline.start_recording()
    if self._led:
        self._led.recording()

def _stop_inline_recording(self):
    """Stop recording and begin transcription."""
    if self._audio_pipeline:
        result = self._audio_pipeline.stop_and_process()
        self._cached_audio_path = getattr(result, 'path', None) if result else None
    self._rec_state = RecState.TRANSCRIBING
    if self._led:
        self._led.sending()
    # Run STT in background
    if self._stt_callable and self._cached_audio_path:
        threading.Thread(target=self._run_stt, daemon=True).start()
    else:
        # No STT available — just trigger handoff with empty text
        self._rec_state = RecState.LAUNCHING
        self._transcribed_text = ""
        self._launch_anim_frame = 0

def _cancel_inline_recording(self):
    """Cancel recording, discard audio, return to READY."""
    if self._audio_pipeline:
        self._audio_pipeline.cancel()
    self._rec_state = RecState.READY
    self._cached_audio_path = None

def _run_stt(self):
    """Background STT. Updates state on completion."""
    try:
        text = self._stt_callable(self._cached_audio_path)
        if text and text.strip():
            self._transcribed_text = text.strip()
            self._rec_state = RecState.LAUNCHING
            self._launch_anim_frame = 0
            if self._led:
                self._led.success()
        else:
            self._rec_state = RecState.ERROR
            self._rec_error_msg = "NO AUDIO DETECTED"
    except Exception:
        self._rec_state = RecState.ERROR
        self._rec_error_msg = "DIDN'T CATCH THAT"
```

**Step 4: Run tests**

Run: `cd /Users/seb/bitos && python -m pytest tests/test_chat_preview.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add device/ui/panels/chat_preview.py tests/test_chat_preview.py
git commit -m "feat: add RecState enum and recording state machine to ChatPreviewPanel"
```

---

### Task 4: Gesture Routing Override

Override `handle_action()` to intercept gestures based on `_rec_state`.

**Files:**
- Modify: `device/ui/panels/chat_preview.py`
- Test: `tests/test_chat_preview.py`

**Step 1: Write failing tests**

```python
def test_double_press_on_record_starts_recording(self):
    """DOUBLE_PRESS on RECORD item should start inline recording."""
    panel = ChatPreviewPanel(on_action=MagicMock())
    from device.ui.panels.chat_preview import RecState
    panel.selected_index = 0  # RECORD item
    panel.handle_action("DOUBLE_PRESS")
    self.assertEqual(panel._rec_state, RecState.RECORDING)

def test_short_press_during_recording_stops(self):
    """SHORT_PRESS during RECORDING should stop recording."""
    panel = ChatPreviewPanel(on_action=MagicMock())
    from device.ui.panels.chat_preview import RecState
    panel._rec_state = RecState.RECORDING
    panel.handle_action("SHORT_PRESS")
    # Should transition to TRANSCRIBING (or ERROR if no pipeline)
    self.assertNotEqual(panel._rec_state, RecState.RECORDING)

def test_long_press_during_recording_cancels(self):
    """LONG_PRESS during RECORDING should cancel."""
    panel = ChatPreviewPanel(on_action=MagicMock())
    from device.ui.panels.chat_preview import RecState
    panel._rec_state = RecState.RECORDING
    panel.handle_action("LONG_PRESS")
    self.assertEqual(panel._rec_state, RecState.READY)

def test_gestures_ignored_during_transcribing(self):
    """All gestures should be swallowed during TRANSCRIBING."""
    panel = ChatPreviewPanel(on_action=MagicMock())
    from device.ui.panels.chat_preview import RecState
    panel._rec_state = RecState.TRANSCRIBING
    panel.selected_index = 0
    panel.handle_action("SHORT_PRESS")
    # selected_index should NOT change
    self.assertEqual(panel.selected_index, 0)
    self.assertEqual(panel._rec_state, RecState.TRANSCRIBING)

def test_short_press_on_error_retries(self):
    panel = ChatPreviewPanel(on_action=MagicMock())
    from device.ui.panels.chat_preview import RecState
    panel._rec_state = RecState.ERROR
    panel.handle_action("SHORT_PRESS")
    self.assertEqual(panel._rec_state, RecState.RECORDING)

def test_normal_items_still_work_in_ready(self):
    """Non-RECORD items should fire normally in READY state."""
    cb = MagicMock()
    panel = ChatPreviewPanel(on_action=cb)
    panel.selected_index = 1  # START NEW CHAT
    panel.handle_action("DOUBLE_PRESS")
    cb.assert_called_once_with("new_chat")
```

**Step 2: Run to verify failure**

Run: `cd /Users/seb/bitos && python -m pytest tests/test_chat_preview.py -v -k "recording or error or ready"`
Expected: FAIL

**Step 3: Implement handle_action override**

In `ChatPreviewPanel`, override `handle_action`:

```python
def handle_action(self, action: str) -> bool:
    """Route gestures based on recording state."""
    # ── Non-READY states: intercept all gestures ──
    if self._rec_state == RecState.RECORDING:
        if action in ("SHORT_PRESS", "DOUBLE_PRESS"):
            self._stop_inline_recording()
        elif action == "LONG_PRESS":
            self._cancel_inline_recording()
        return True

    if self._rec_state in (RecState.TRANSCRIBING, RecState.LAUNCHING):
        return True  # swallow everything

    if self._rec_state == RecState.ERROR:
        if action == "SHORT_PRESS":
            self._start_inline_recording()  # retry
        elif action == "LONG_PRESS":
            self._rec_state = RecState.READY  # give up
        return True

    # ── READY state: check if activating the RECORD item ──
    if action == "DOUBLE_PRESS" and self.selected_index >= 0:
        item = self.items[self.selected_index]
        if item.get("action") == "respond":
            self._start_inline_recording()
            return True

    # Fall through to normal PreviewPanel behavior
    return super().handle_action(action)
```

**Step 4: Run tests**

Run: `cd /Users/seb/bitos && python -m pytest tests/test_chat_preview.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add device/ui/panels/chat_preview.py tests/test_chat_preview.py
git commit -m "feat: gesture routing override for inline recording states"
```

---

### Task 5: Recording Row Rendering (Pulsing Dot + Timer)

Custom rendering for the RECORD row in each state.

**Files:**
- Modify: `device/ui/panels/chat_preview.py`

**Step 1: Update the RECORD item subtext**

Change in `CHAT_ITEMS`:
```python
{"label": "RECORD", "description": "Reply to greeting", "action": "respond", "subtext": "Double-click to record"},
```

**Step 2: Add custom row rendering in render()**

After the existing `self._render_items(surface, y_offset=greeting_h)` call, add an override that draws custom content for the RECORD row when not in READY state. The cleanest approach: override `_render_items` or post-render over the RECORD row area.

Add a `_render_record_row()` method:

```python
def _render_record_row(self, surface: pygame.Surface, y: int, w: int) -> int:
    """Render the RECORD row based on current _rec_state. Returns row height."""
    from device.ui.panels.base import ITEM_H, PAD_X, PAD_Y, FONT_SIZE
    font = get_font(FONT_SIZE)
    subtext_font = get_font(FONT_SIZE - 2)

    if self._rec_state == RecState.RECORDING:
        # Red-tinted background
        now = time.time()
        bg_pulse = (math.sin(now * 1.0 * 2 * math.pi) + 1) / 2  # 1Hz
        bg_r = int(25 + 30 * bg_pulse)
        pygame.draw.rect(surface, (bg_r, 5, 5), pygame.Rect(0, y, w, ITEM_H))

        # Pulsing red dot
        dot_pulse = (math.sin(now * 2.0 * 2 * math.pi) + 1) / 2  # 2Hz
        dot_bright = int(140 + 115 * dot_pulse)
        dot_r = 4 + int(dot_pulse)
        pygame.draw.circle(surface, (dot_bright, 20, 20),
                          (PAD_X + 6, y + ITEM_H // 2), dot_r)

        # Timer text
        elapsed = int(now - self._rec_start_time)
        mins, secs = divmod(elapsed, 60)
        timer_text = f"REC {mins}:{secs:02d}"
        timer_surf = font.render(timer_text, False, (220, 80, 80))
        surface.blit(timer_surf, (PAD_X + 14, y + PAD_Y))

        # Subtext hint
        hint = subtext_font.render("  Click to stop", False, DIM3)
        surface.blit(hint, (PAD_X, y + PAD_Y + font.get_height() + 1))
        return ITEM_H + subtext_font.get_height() + 2

    elif self._rec_state == RecState.TRANSCRIBING:
        # Animated dots
        dot_count = (int(time.time() * 3.75) % 4)  # ~267ms per dot at any FPS
        dots = "." * dot_count
        text_surf = font.render("TRANSCRIBING" + dots, False, DIM2)
        surface.blit(text_surf, (PAD_X, y + PAD_Y))
        return ITEM_H

    elif self._rec_state == RecState.LAUNCHING:
        # Expanding row
        h = self._launch_current_h
        pygame.draw.rect(surface, (30, 30, 30), pygame.Rect(0, y, w, h))
        text_surf = font.render("STARTING CONVERSATION...", False, WHITE)
        tx = (w - text_surf.get_width()) // 2
        ty = y + (h - text_surf.get_height()) // 2
        surface.blit(text_surf, (tx, ty))
        return h

    elif self._rec_state == RecState.ERROR:
        text_surf = font.render(self._rec_error_msg or "ERROR", False, (220, 80, 80))
        surface.blit(text_surf, (PAD_X, y + PAD_Y))
        hint = subtext_font.render("  Click to retry", False, DIM3)
        surface.blit(hint, (PAD_X, y + PAD_Y + font.get_height() + 1))
        return ITEM_H + subtext_font.get_height() + 2

    return ITEM_H  # READY — handled by base _render_items
```

**Step 3: Override render to use custom row**

Replace the end of `render()` where `_render_items` is called. When `_rec_state != READY`, render the RECORD row custom, then render remaining items below it with dimmed colors:

```python
# In render(), replace the final self._render_items line:
if self._rec_state == RecState.READY:
    self._render_items(surface, y_offset=greeting_h)
else:
    self._render_record_row_and_dimmed_items(surface, greeting_h)
```

Add helper:
```python
def _render_record_row_and_dimmed_items(self, surface: pygame.Surface, y_offset: int) -> None:
    """Render custom RECORD row + dimmed remaining items."""
    from device.ui.panels.base import ITEM_H, PAD_X, PAD_Y, FONT_SIZE, HAIRLINE
    font = get_font(FONT_SIZE)
    w = surface.get_width()

    y = y_offset
    # Custom RECORD row
    row_h = self._render_record_row(surface, y, w)
    y += row_h

    # Remaining items (dimmed, non-interactive)
    subtext_font = get_font(FONT_SIZE - 2)
    for item in self.items[1:]:  # skip RECORD (index 0)
        label = "  " + item["label"]
        text_surf = font.render(label, False, HAIRLINE)  # very dim
        surface.blit(text_surf, (PAD_X, y + PAD_Y))

        item_h = ITEM_H
        subtext = item.get("subtext")
        if subtext:
            sub_surf = subtext_font.render("  " + subtext, False, HAIRLINE)
            surface.blit(sub_surf, (PAD_X, y + PAD_Y + font.get_height() + 1))
            item_h = ITEM_H + subtext_font.get_height() + 2

        if y + item_h - 1 < surface.get_height():
            pygame.draw.line(surface, HAIRLINE,
                           (PAD_X, y + item_h - 1), (w - PAD_X, y + item_h - 1))
        y += item_h
```

**Step 4: Test manually**

Run: `cd /Users/seb/bitos && python -m pytest tests/test_chat_preview.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add device/ui/panels/chat_preview.py
git commit -m "feat: custom RECORD row rendering (pulsing dot, timer, transcribing, launching)"
```

---

### Task 6: Update Loop — Expansion Animation + Handoff

Wire the `update()` method to advance the expansion animation and trigger handoff.

**Files:**
- Modify: `device/ui/panels/chat_preview.py`
- Test: `tests/test_chat_preview.py`

**Step 1: Write failing test**

```python
def test_launching_animation_advances(self):
    panel = ChatPreviewPanel(on_action=MagicMock())
    from device.ui.panels.chat_preview import RecState
    panel._rec_state = RecState.LAUNCHING
    panel._launch_anim_frame = 0
    panel._transcribed_text = "hello"
    panel.update(1 / 15)  # one frame
    self.assertEqual(panel._launch_anim_frame, 1)
    self.assertGreater(panel._launch_current_h, 22)

def test_launching_triggers_handoff(self):
    cb = MagicMock()
    panel = ChatPreviewPanel(on_action=cb)
    from device.ui.panels.chat_preview import RecState
    panel._rec_state = RecState.LAUNCHING
    panel._transcribed_text = "test message"
    # Advance past all animation frames
    for _ in range(10):
        panel.update(1 / 15)
    cb.assert_called_once_with("respond_with_text")
```

**Step 2: Run to verify failure**

Run: `cd /Users/seb/bitos && python -m pytest tests/test_chat_preview.py -v -k "launching"`
Expected: FAIL

**Step 3: Implement update() changes**

Update the existing `update()` method:

```python
def update(self, dt: float) -> None:
    self._cursor_anim.update(dt)
    if self._greeting_typewriter and not self._greeting_typewriter.finished:
        self._greeting_typewriter.update(dt)
    elif self._greeting_typewriter and self._greeting_typewriter.finished:
        self._greeting_revealed = True
        self._greeting_typewriter = None

    # Expansion animation during LAUNCHING
    if self._rec_state == RecState.LAUNCHING:
        self._launch_anim_frame += 1
        t = min(1.0, self._launch_anim_frame / self._launch_anim_duration)
        # ease_out_cubic
        eased = 1 - (1 - t) ** 3
        from device.ui.panels.base import ITEM_H
        self._launch_current_h = int(ITEM_H + (self._launch_target_h - ITEM_H) * eased)

        if t >= 1.0:
            # Animation done — trigger handoff
            self._rec_state = RecState.READY
            self._launch_current_h = ITEM_H  # reset
            self._on_action("respond_with_text")
```

**Step 4: Run tests**

Run: `cd /Users/seb/bitos && python -m pytest tests/test_chat_preview.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add device/ui/panels/chat_preview.py tests/test_chat_preview.py
git commit -m "feat: expansion animation + handoff trigger in update loop"
```

---

### Task 7: Wire Panel Registry — Pass Audio + STT + LED

Update `panel_registry.py` to pass audio pipeline and STT callable to ChatPreviewPanel.

**Files:**
- Modify: `device/ui/panel_registry.py:33, 91`
- Modify: `device/ui/panels/chat_preview.py:38` (constructor signature)

**Step 1: Update ChatPreviewPanel constructor**

```python
def __init__(self, on_action: callable, repository=None,
             audio_pipeline=None, stt_callable=None, led=None):
    items = [dict(item) for item in CHAT_ITEMS]
    super().__init__(items=items, on_action=on_action)
    self._repository = repository
    # ... existing init ...
    # Wire audio
    self._audio_pipeline = audio_pipeline
    self._stt_callable = stt_callable
    self._led = led
```

Remove the separate `set_audio_pipeline()` and `set_stt_callable()` methods (pass through constructor instead).

**Step 2: Update panel_registry.py**

Add parameters to `create_right_panels`:

```python
def create_right_panels(panel_openers: dict | None = None, repository=None,
                        status_state=None, audio_pipeline=None,
                        stt_callable=None, led=None) -> dict:
```

Update the ChatPreviewPanel construction:

```python
panels["CHAT"] = ChatPreviewPanel(
    on_action=chat_action,
    repository=repository,
    audio_pipeline=audio_pipeline,
    stt_callable=stt_callable,
    led=led,
)
```

**Step 3: Update chat_action to handle respond_with_text**

In `panel_registry.py`, update the `chat_action` function:

```python
def chat_action(action_key):
    if action_key == "back":
        return
    if action_key == "respond_with_text":
        # Get transcribed text from the panel and pass to opener
        panel = panels.get("CHAT")
        text = panel._transcribed_text if panel else None
        opener = openers.get("CHAT_RESPOND_TEXT") or openers.get("CHAT_GREETING") or openers.get("CHAT")
        if opener is not None:
            opener(text=text)
        return
    if action_key == "respond":
        opener = openers.get("CHAT_GREETING") or openers.get("CHAT")
        if opener is not None:
            opener()
        return
    # ... rest unchanged ...
```

**Step 4: Run existing tests**

Run: `cd /Users/seb/bitos && python -m pytest tests/test_chat_preview.py tests/test_panel_shells.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add device/ui/panels/chat_preview.py device/ui/panel_registry.py
git commit -m "feat: wire audio pipeline + STT through panel registry to ChatPreviewPanel"
```

---

### Task 8: Action Bar Hints for Recording States

Update the action bar hints when the panel enters recording states, so the user sees the right gesture labels.

**Files:**
- Modify: `device/ui/composite_screen.py`

**Step 1: Implement**

In `CompositeScreen._handle_submenu_action()`, after routing to the panel, check if the active panel has a recording state and update hints accordingly:

```python
def _handle_submenu_action(self, action: str) -> None:
    if action == "LONG_PRESS":
        # Check if panel is in recording state — LONG cancels recording, not exit submenu
        panel = self._active_panel()
        if panel and hasattr(panel, '_rec_state'):
            from device.ui.panels.chat_preview import RecState
            if panel._rec_state in (RecState.RECORDING, RecState.ERROR):
                panel.handle_action(action)
                self._update_action_bar_for_rec_state(panel)
                return
        self._exit_submenu()
        return

    panel = self._active_panel()
    if panel is not None and hasattr(panel, "handle_action"):
        if action == "DOUBLE_PRESS" and hasattr(panel, "items") and hasattr(panel, "selected_index"):
            item = panel.items[panel.selected_index]
            if item.get("action") == "back":
                self._exit_submenu()
                return
        panel.handle_action(action)
        # Update hints after action
        if hasattr(panel, '_rec_state'):
            self._update_action_bar_for_rec_state(panel)
```

Add the hint updater:

```python
_REC_ACTIONS = [
    ("tap", "STOP"),
    ("hold", "CANCEL"),
]

_REC_PROCESSING_ACTIONS = []  # no actions during processing

def _update_action_bar_for_rec_state(self, panel) -> None:
    from device.ui.panels.chat_preview import RecState
    if panel._rec_state == RecState.RECORDING:
        self._action_bar.set_actions(self._REC_ACTIONS)
    elif panel._rec_state in (RecState.TRANSCRIBING, RecState.LAUNCHING):
        self._action_bar.set_actions(self._REC_PROCESSING_ACTIONS)
    elif panel._rec_state == RecState.ERROR:
        self._action_bar.set_actions([("tap", "RETRY"), ("hold", "CANCEL")])
    else:
        self._action_bar.set_actions(self._SUBMENU_ACTIONS)
```

**Step 2: Run tests**

Run: `cd /Users/seb/bitos && python -m pytest tests/ -v -k "composite or chat_preview" --timeout=10`
Expected: All PASS

**Step 3: Commit**

```bash
git add device/ui/composite_screen.py
git commit -m "feat: dynamic action bar hints for recording states"
```

---

### Task 9: Integration Test — Full Recording Flow

End-to-end test with mocked audio pipeline.

**Files:**
- Test: `tests/test_chat_preview.py`

**Step 1: Write integration test**

```python
def test_full_recording_flow(self):
    """DOUBLE on RECORD → recording → SHORT → transcribing → launching → handoff."""
    cb = MagicMock()
    from device.ui.panels.chat_preview import RecState

    mock_pipeline = MagicMock()
    mock_pipeline.stop_and_process.return_value = MagicMock(path="/tmp/test.wav")

    def mock_stt(path):
        return "hello world"

    panel = ChatPreviewPanel(
        on_action=cb,
        audio_pipeline=mock_pipeline,
        stt_callable=mock_stt,
    )
    panel.selected_index = 0

    # Start recording
    panel.handle_action("DOUBLE_PRESS")
    self.assertEqual(panel._rec_state, RecState.RECORDING)
    mock_pipeline.start_recording.assert_called_once()

    # Stop recording
    panel.handle_action("SHORT_PRESS")
    # STT runs in background thread — give it a moment
    import time
    time.sleep(0.2)
    self.assertEqual(panel._rec_state, RecState.LAUNCHING)
    self.assertEqual(panel._transcribed_text, "hello world")

    # Advance animation to completion
    for _ in range(10):
        panel.update(1 / 15)
    cb.assert_called_with("respond_with_text")
```

**Step 2: Run**

Run: `cd /Users/seb/bitos && python -m pytest tests/test_chat_preview.py::ChatPreviewTests::test_full_recording_flow -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_chat_preview.py
git commit -m "test: integration test for full inline recording flow"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Fix existing test for MAX_GREETING_CHARS | test_chat_preview.py |
| 2 | Dynamic greeting height (40-100px) | chat_preview.py, test |
| 3 | RecState enum + state machine skeleton | chat_preview.py, test |
| 4 | Gesture routing override | chat_preview.py, test |
| 5 | Recording row rendering (pulse, timer, dots, expand) | chat_preview.py |
| 6 | Update loop — expansion animation + handoff | chat_preview.py, test |
| 7 | Wire panel registry — audio + STT + LED | panel_registry.py, chat_preview.py |
| 8 | Action bar hints for recording states | composite_screen.py |
| 9 | Integration test — full flow | test_chat_preview.py |
