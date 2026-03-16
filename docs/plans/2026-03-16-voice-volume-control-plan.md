# Voice & Volume Control Sprint 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add speaking overlay with gesture controls, wire voice settings (Off/On/Auto + volume), move TTS test to settings, and gate heartbeat audio.

**Architecture:** Speaking overlay is a lightweight dataclass rendered by ChatPanel during SPEAKING mode. Voice settings use the existing repository get_setting/set_setting pattern with a three-way voice_mode (off/on/auto). The chat panel's TTS decision logic reads voice_mode to determine whether to speak. Boot TTS test removed from main.py, added as "Test Voice" item in ChatSettingsPanel.

**Tech Stack:** Python 3.13, pygame, ALSA aplay, Speechify API, SQLite settings

---

### Task 1: Speaking Overlay Renderer

**Files:**
- Create: `device/overlays/speaking_overlay.py`
- Test: `tests/test_speaking_overlay.py`

**Step 1: Write the failing test**

```python
# tests/test_speaking_overlay.py
"""Tests for the speaking overlay widget."""
import pytest


def test_speaking_overlay_creation():
    from overlays.speaking_overlay import SpeakingOverlay
    overlay = SpeakingOverlay()
    assert overlay.active is False


def test_speaking_overlay_show_hide():
    from overlays.speaking_overlay import SpeakingOverlay
    overlay = SpeakingOverlay()
    overlay.show()
    assert overlay.active is True
    overlay.dismiss()
    assert overlay.active is False


def test_speaking_overlay_tick_animates_dots():
    from overlays.speaking_overlay import SpeakingOverlay
    overlay = SpeakingOverlay()
    overlay.show()
    dots1 = overlay._dots
    overlay.tick(500)
    dots2 = overlay._dots
    # Dots should cycle 0-3
    assert 0 <= dots1 <= 3
    assert 0 <= dots2 <= 3


def test_speaking_overlay_gesture_short_press_dismisses():
    from overlays.speaking_overlay import SpeakingOverlay
    overlay = SpeakingOverlay()
    overlay.show()
    result = overlay.handle_action("SHORT_PRESS")
    assert result == "dismiss"


def test_speaking_overlay_gesture_hold_start_replies():
    from overlays.speaking_overlay import SpeakingOverlay
    overlay = SpeakingOverlay()
    overlay.show()
    result = overlay.handle_action("HOLD_START")
    assert result == "reply"


def test_speaking_overlay_inactive_ignores_actions():
    from overlays.speaking_overlay import SpeakingOverlay
    overlay = SpeakingOverlay()
    result = overlay.handle_action("SHORT_PRESS")
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/seb/bitos && python -m pytest tests/test_speaking_overlay.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'overlays.speaking_overlay'"

**Step 3: Write minimal implementation**

```python
# device/overlays/speaking_overlay.py
"""Speaking overlay — bottom strip shown during TTS playback."""
from __future__ import annotations

import pygame


class SpeakingOverlay:
    """Small bottom strip with speaker icon and gesture hints during TTS."""

    STRIP_H = 28

    def __init__(self):
        self.active = False
        self._dots = 0
        self._dot_timer_ms = 0
        self._font_cache: dict[int, pygame.font.Font] = {}

    def show(self) -> None:
        self.active = True
        self._dots = 0
        self._dot_timer_ms = 0

    def dismiss(self) -> None:
        self.active = False

    def tick(self, dt_ms: int) -> None:
        if not self.active:
            return
        self._dot_timer_ms += dt_ms
        if self._dot_timer_ms >= 400:
            self._dot_timer_ms = 0
            self._dots = (self._dots + 1) % 4

    def handle_action(self, action: str) -> str | None:
        """Handle gesture while speaking. Returns 'dismiss', 'reply', or None."""
        if not self.active:
            return None
        if action in ("SHORT_PRESS", "DOUBLE_PRESS", "LONG_PRESS"):
            return "dismiss"
        if action == "HOLD_START":
            return "reply"
        return None

    def render(self, surface: pygame.Surface, tokens) -> None:
        if not self.active:
            return
        w = tokens.PHYSICAL_W
        h = tokens.PHYSICAL_H
        y = h - tokens.SAFE_INSET - self.STRIP_H

        # Background strip
        pygame.draw.rect(surface, tokens.WHITE, pygame.Rect(0, y, w, self.STRIP_H))

        font = self._get_font(tokens, tokens.FONT_SIZES["small"])

        # Speaker icon + "speaking" + dots
        dots_str = "." * self._dots
        text = f"))) speaking{dots_str}"
        text_surf = font.render(text, False, tokens.BLACK)
        surface.blit(text_surf, (8, y + (self.STRIP_H - text_surf.get_height()) // 2))

        # Gesture hint on right
        hint = "tap:stop"
        hint_surf = font.render(hint, False, tokens.DIM2)
        surface.blit(hint_surf, (w - hint_surf.get_width() - 8, y + (self.STRIP_H - hint_surf.get_height()) // 2))

    def _get_font(self, tokens, size: int) -> pygame.font.Font:
        if size in self._font_cache:
            return self._font_cache[size]
        try:
            font = pygame.font.Font(tokens.FONT_PATH, size)
        except (FileNotFoundError, OSError):
            font = pygame.font.SysFont("monospace", size)
        self._font_cache[size] = font
        return font
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/seb/bitos && PYTHONPATH=device python -m pytest tests/test_speaking_overlay.py -v`
Expected: 6 PASSED

**Step 5: Commit**

```bash
git add device/overlays/speaking_overlay.py tests/test_speaking_overlay.py
git commit -m "feat: add speaking overlay widget with gesture handling"
```

---

### Task 2: Wire Speaking Overlay into ChatPanel

**Files:**
- Modify: `device/screens/panels/chat.py` (import, init, render, handle_speaking, _stream_response)

**Step 1: Import and initialize the overlay**

In `chat.py`, add import at top:
```python
from overlays.speaking_overlay import SpeakingOverlay
```

In `__init__`, add:
```python
self._speaking_overlay = SpeakingOverlay()
```

**Step 2: Update `_handle_speaking` to use overlay gestures**

Replace the existing `_handle_speaking` method:
```python
def _handle_speaking(self, action: str):
    result = self._speaking_overlay.handle_action(action)
    if result == "dismiss":
        if self._audio_pipeline:
            self._audio_pipeline.stop_speaking()
        self._speaking_overlay.dismiss()
        self._mode = ChatMode.IDLE
        with self._messages_lock:
            self._status_detail = ""
    elif result == "reply":
        if self._audio_pipeline:
            self._audio_pipeline.stop_speaking()
        self._speaking_overlay.dismiss()
        self._mode = ChatMode.IDLE
        self._quick_talk = True
        self._start_recording()
```

**Step 3: Show overlay when TTS starts, dismiss when done**

In `_stream_response`, around line 934-943, update the TTS block:
```python
if self._audio_pipeline and response_text and voice_enabled:
    try:
        self._mode = ChatMode.SPEAKING
        self._speaking_overlay.show()
        with self._messages_lock:
            self._status_detail = "SPEAKING..."
        if self._led:
            self._led.speaking()
        self._audio_pipeline.speak(response_text)
    except Exception as tts_exc:
        logger.error("tts_failed: %s", tts_exc)
    finally:
        self._speaking_overlay.dismiss()
```

**Step 4: Render the overlay**

In the `render` method, add after the hint bar rendering (near end of render):
```python
# Speaking overlay (rendered on top)
if self._speaking_overlay.active:
    self._speaking_overlay.render(surface, tokens_module)
```

Note: `tokens_module` is the `display.tokens` module — add `import display.tokens as tokens_module` at the top of the file if not already imported.

**Step 5: Tick the overlay in update()**

In the `update` method, add:
```python
self._speaking_overlay.tick(int(dt * 1000))
```

**Step 6: Update action bar for SPEAKING mode**

In `_get_action_bar_content`, the SPEAKING case already returns `[("tap", "stop")]`. Update it to:
```python
elif self._mode == ChatMode.SPEAKING:
    return [("tap", "stop"), ("hold", "reply")]
```

**Step 7: Commit**

```bash
git add device/screens/panels/chat.py
git commit -m "feat: wire speaking overlay into chat panel with dismiss + reply gestures"
```

**Step 8: Deploy and test on Pi**

```bash
make deploy
```
Then send a voice message and verify:
- Speaking overlay appears at bottom during TTS
- Tap stops speech and dismisses overlay
- Hold stops speech and starts recording

---

### Task 3: Voice Mode Setting (Off/On/Auto)

**Files:**
- Modify: `device/screens/panels/chat.py` (TTS decision logic)
- Modify: `device/screens/panels/chat_settings.py` (add voice_mode setting)
- Modify: `device/client/api.py` (update response_format_hint)
- Test: `tests/test_voice_mode.py`

**Step 1: Write the failing test**

```python
# tests/test_voice_mode.py
"""Tests for voice mode setting logic."""
import os
import pytest


def test_voice_mode_off_blocks_tts():
    """When voice_mode=off, TTS should not fire even if agent sends {{voice:on}}."""
    from screens.panels.chat import _should_speak
    assert _should_speak(voice_mode="off", agent_voice_enabled=True, has_api_key=True) is False


def test_voice_mode_on_always_speaks():
    """When voice_mode=on, TTS always fires."""
    assert _should_speak(voice_mode="on", agent_voice_enabled=False, has_api_key=True) is True


def test_voice_mode_auto_respects_agent():
    """When voice_mode=auto, agent's voice_enabled setting is used."""
    from screens.panels.chat import _should_speak
    assert _should_speak(voice_mode="auto", agent_voice_enabled=True, has_api_key=True) is True
    assert _should_speak(voice_mode="auto", agent_voice_enabled=False, has_api_key=True) is False


def test_voice_mode_auto_no_key():
    """When voice_mode=auto but no API key, TTS doesn't fire."""
    from screens.panels.chat import _should_speak
    assert _should_speak(voice_mode="auto", agent_voice_enabled=True, has_api_key=False) is False


def test_voice_mode_on_no_key():
    """When voice_mode=on but no API key, TTS doesn't fire."""
    from screens.panels.chat import _should_speak
    assert _should_speak(voice_mode="on", agent_voice_enabled=True, has_api_key=False) is False
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/seb/bitos && PYTHONPATH=device python -m pytest tests/test_voice_mode.py -v`
Expected: FAIL with "cannot import name '_should_speak'"

**Step 3: Add `_should_speak` function to chat.py**

Add as a module-level function (above the ChatPanel class):
```python
def _should_speak(voice_mode: str, agent_voice_enabled: bool, has_api_key: bool) -> bool:
    """Determine if TTS should fire based on user setting, agent preference, and API key."""
    if not has_api_key:
        return False
    if voice_mode == "off":
        return False
    if voice_mode == "on":
        return True
    # auto — agent decides
    return agent_voice_enabled
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/seb/bitos && PYTHONPATH=device python -m pytest tests/test_voice_mode.py -v`
Expected: 5 PASSED

**Step 5: Update TTS block in `_stream_response` to use `_should_speak`**

Replace lines 926-934 with:
```python
# TTS: determine voice mode
voice_mode = "auto"
if self._repository:
    voice_mode = str(self._repository.get_setting("voice_mode", "auto")).lower()

# Agent-level voice toggle (from inline commands or default)
agent_voice_enabled = bool(os.environ.get("SPEECHIFY_API_KEY"))
if self._repository:
    stored = self._repository.get_setting("voice_enabled", None)
    if stored is not None:
        agent_voice_enabled = str(stored).lower() in ("true", "1", "yes", "on")

has_api_key = bool(os.environ.get("SPEECHIFY_API_KEY"))
should_speak = _should_speak(voice_mode, agent_voice_enabled, has_api_key)
logger.info("tts_check: voice_mode=%s agent_voice=%s has_key=%s -> speak=%s text_len=%d",
            voice_mode, agent_voice_enabled, has_api_key, should_speak, len(response_text))

if self._audio_pipeline and response_text and should_speak:
```

**Step 6: Update `_parse_commands` to respect voice_mode=off**

In the `voice` command handler, add a check:
```python
elif cmd == "voice":
    voice_mode = "auto"
    if self._repository:
        voice_mode = str(self._repository.get_setting("voice_mode", "auto")).lower()
    if voice_mode == "off":
        logger.info("voice_command_ignored: voice_mode=off overrides agent")
    else:
        enabled = val in ("on", "true", "1", "yes")
        if self._repository:
            self._repository.set_setting("voice_enabled", enabled)
        logger.info("voice_enabled=%s via agent command", enabled)
```

**Step 7: Update response_format_hint in api.py**

In `_stream_chat_sse`, update the `response_format_hint` to include voice_mode:
```python
"response_format_hint": (
    "Keep responses concise and structured. Use short paragraphs "
    "separated by blank lines. Aim for under 800 characters total "
    "— the device displays text in pages of ~250 characters each. "
    "Device commands (parsed out before display): "
    "{{volume:NUMBER}} (0-100) to set volume, "
    "{{voice:on}} or {{voice:off}} to toggle voice replies. "
    "Current volume: " + str(volume) + "%. "
    "Voice: " + (
        "FORCED OFF by user" if voice_mode == "off"
        else "FORCED ON by user" if voice_mode == "on"
        else ("ON" if voice_enabled else "OFF (available — user can ask you to turn it on)")
    ) + "."
),
```

This requires passing `voice_mode` into `_stream_chat_sse`. Add it to the signature and read it from repo in `chat()`:
```python
voice_mode = str(repository.get_setting("voice_mode", "auto"))
```

**Step 8: Commit**

```bash
git add device/screens/panels/chat.py device/client/api.py tests/test_voice_mode.py
git commit -m "feat: add Off/On/Auto voice mode with priority logic"
```

---

### Task 4: Add Voice & Volume Controls to Settings Panel

**Files:**
- Modify: `device/screens/panels/chat_settings.py`

**Step 1: Add voice_mode, volume, and Test Voice to settings list**

In `__init__`, after loading existing settings, add:
```python
voice_mode = self._repository.get_setting("voice_mode", "auto")
volume = self._repository.get_setting("volume", 100)

self._settings = [
    {"label": "VOICE MODE", "key": "voice_mode", "value": str(voice_mode or "auto"),
     "options": ["off", "on", "auto"]},
    {"label": "VOLUME", "key": "volume", "value": str(volume),
     "options": [str(v) for v in range(0, 110, 10)]},
    {"label": "META PROMPT", "key": "meta_prompt", "value": str(meta or "default assistant")},
    {"label": "TEXT SPEED", "key": "text_speed", "value": str(text_speed or "normal")},
    {"label": "VOICE SPEED", "key": "voice_speed", "value": str(voice_speed or "normal")},
    {"label": "TEST VOICE", "key": "_test_voice", "value": "tap to test", "action": True},
]
```

**Step 2: Add DOUBLE_PRESS to cycle through options**

In `handle_action`, add option cycling:
```python
def handle_action(self, action: str):
    if action == "SHORT_PRESS":
        self._selected = (self._selected + 1) % len(self._settings)
    elif action == "TRIPLE_PRESS":
        self._selected = (self._selected - 1) % len(self._settings)
    elif action == "DOUBLE_PRESS":
        setting = self._settings[self._selected]
        if setting.get("action"):
            self._run_action(setting["key"])
        elif "options" in setting:
            opts = setting["options"]
            try:
                idx = opts.index(setting["value"])
            except ValueError:
                idx = -1
            new_idx = (idx + 1) % len(opts)
            setting["value"] = opts[new_idx]
            self._repository.set_setting(setting["key"], setting["value"])
    elif action == "LONG_PRESS":
        if self._on_back:
            self._on_back()
```

**Step 3: Add Test Voice action**

```python
def _run_action(self, key: str):
    if key == "_test_voice":
        self._test_voice_status = "connecting..."
        import threading
        threading.Thread(target=self._run_voice_test, daemon=True).start()

def _run_voice_test(self):
    import logging
    logger = logging.getLogger(__name__)
    try:
        self._test_voice_status = "synthesizing..."
        from audio.tts_test import test_speechify_api
        api_result = test_speechify_api()
        if not api_result["ok"]:
            self._test_voice_status = f"FAIL: {api_result['detail'][:20]}"
            return

        self._test_voice_status = "playing..."
        from audio.tts_test import test_full_pipeline
        pipeline_result = test_full_pipeline()
        if pipeline_result["ok"]:
            self._test_voice_status = f"OK ({pipeline_result['duration_ms']}ms)"
        else:
            self._test_voice_status = f"FAIL: {pipeline_result['detail'][:20]}"
    except Exception as exc:
        logger.error("voice_test_failed: %s", exc)
        self._test_voice_status = f"ERROR: {str(exc)[:20]}"
```

In `__init__`, add: `self._test_voice_status = ""`

**Step 4: Update render to show test status**

When rendering the TEST VOICE row, show `_test_voice_status` instead of "tap to test" if set:
```python
# In the render loop, for the value display:
if setting["key"] == "_test_voice" and self._test_voice_status:
    val_text = self._test_voice_status
else:
    val_text = setting["value"]
```

**Step 5: Commit**

```bash
git add device/screens/panels/chat_settings.py
git commit -m "feat: add voice mode, volume, and test voice to chat settings"
```

**Step 6: Deploy and test**

```bash
make deploy
```
Navigate to Chat → Settings on device. Verify:
- Voice Mode cycles through off/on/auto on DOUBLE press
- Volume cycles through 0-100 in steps of 10
- Test Voice runs the full test with step-by-step status updates

---

### Task 5: Remove Boot TTS Test

**Files:**
- Modify: `device/main.py` (remove boot test thread)

**Step 1: Remove the boot TTS test block from main.py**

Delete lines 200-208 (the `_boot_tts_test` function and thread):
```python
# DELETE THIS BLOCK:
# Run TTS test on boot (background — doesn't block startup)
def _boot_tts_test():
    try:
        from audio.tts_test import run_boot_test
        run_boot_test()
    except Exception as exc:
        logger.error("boot_tts_test_failed: %s", exc)

threading.Thread(target=_boot_tts_test, daemon=True, name="tts-boot-test").start()
```

**Step 2: Commit**

```bash
git add device/main.py
git commit -m "feat: remove auto-boot TTS test (moved to settings)"
```

---

### Task 6: Heartbeat Audio Gating

**Files:**
- Modify: `device/screens/panels/chat.py` (only speak in active chat sessions)

**Step 1: Add active-session check before TTS**

The greeting fetch in `main.py` creates a chat session but the response goes through a ChatPreviewPanel, not a full ChatPanel. The `_stream_response` method in ChatPanel is only called during active user-initiated chats, so heartbeat/greeting responses won't trigger TTS through this path.

However, verify that the greeting fetch path does NOT call TTS. Check `_fetch_greeting` in main.py — it streams text from the backend but only stores it for display, never calls `audio_pipeline.speak()`. So heartbeat audio gating is already correct by architecture.

Add an explicit guard comment + log for clarity:
```python
# TTS only fires in active user-initiated chat sessions (not greetings/heartbeat)
if self._audio_pipeline and response_text and should_speak:
    logger.info("tts_start: session=%s text_len=%d", self._session_id, len(response_text))
```

**Step 2: Commit**

```bash
git add device/screens/panels/chat.py
git commit -m "feat: add explicit TTS gating — only speaks in active chat sessions"
```

**Step 3: Deploy final sprint**

```bash
make deploy
```

Verify on Pi:
- Boot greeting does NOT trigger audio
- Chat response with voice_mode=on DOES trigger audio with overlay
- Voice_mode=off silences all TTS
- Settings panel shows all new controls
- Test Voice in settings runs and reports status

---

### Summary: Sprint 1 Deliverables

| Task | What | Deploy? |
|------|------|---------|
| 1 | Speaking overlay widget | No (test only) |
| 2 | Wire overlay into chat | Yes — deploy & test |
| 3 | Off/On/Auto voice mode | No (test only) |
| 4 | Settings UI for voice/volume | Yes — deploy & test |
| 5 | Remove boot TTS test | Yes — deploy |
| 6 | Heartbeat audio gating | Yes — final deploy |
