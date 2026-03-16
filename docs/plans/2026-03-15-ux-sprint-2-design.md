# BITOS UX Sprint 2 — Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix voice chat flow, display clipping, and hint bar to make the device usable day-to-day. Build input routing architecture that supports future hardware (second button, scroll wheel).

**Architecture:** Five independent pillars: chat input state machine → safe area system → action bar → typewriter renderer → flicker investigation. Each is independently shippable.

**Constraints:** 240x280 ST7789 display, single-button navigation, 15 FPS pygame, Pi Zero 2W.

---

## Pillar 1: Chat Input State Machine

### Problem
Recording mode doesn't isolate its input handling. Button presses fall through to the action menu logic, and the stop mechanism polls a boolean flag in a thread at 100ms intervals — unreliable. Users can't stop recording; LONG_PRESS exits chat entirely instead of canceling the recording.

### New Architecture
Remove the SPEAK/ACTIONS/BACK action menu. Replace with gesture-driven modes — **the gestures ARE the interface.**

**Input modes (enum):**
```
IDLE       → viewing chat history (default on entering chat)
RECORDING  → capturing audio
ACTIONS    → quick actions menu overlay
STREAMING  → response arriving (typewriter animation)
SPEAKING   → TTS playing response
```

**Gesture mapping per mode:**

| Mode | HOLD (>400ms) | SHORT TAP | DOUBLE TAP | LONG PRESS |
|------|---------------|-----------|------------|------------|
| IDLE | Start recording → RECORDING | Scroll messages | Open quick actions → ACTIONS | Exit chat (back) |
| RECORDING | *(already recording)* | Send recording → STREAMING | Send recording → STREAMING | Cancel → IDLE |
| ACTIONS | — | Next item | Select item → STREAMING | Back → IDLE |
| STREAMING | — | *(ignored)* | *(ignored)* | *(ignored)* |
| SPEAKING | — | Stop audio → IDLE | Stop audio → IDLE | Stop audio → IDLE |

### Recording trigger
- `HOLD_START` event fires on button press, starts a timer
- If button still held after 400ms, recording begins (IDLE → RECORDING)
- If released before 400ms, it's a SHORT_PRESS (scroll)
- In RECORDING mode, LONG_PRESS is ignored (already handled by mode)
- Stop recording via `threading.Event` — no more boolean flag polling with sleep loops

### Recording UI
- Pulsing red `●REC` in status bar + elapsed time counter
- Simple volume meter bar (horizontal, audio level from pipeline)
- Action bar shows: `○ SEND  ● CANCEL`

### Voice pipeline
- Record → stop → transcribe → send (synchronous within thread)
- Proper error handling: network errors, transcription failures, empty audio
- Future: streaming/chunked transcription (out of scope)

### Quick actions (ACTIONS mode)
- Overlay replaces message area with template list
- 3-4 templated prompts (configurable, stored in repository)
- SHORT cycles, DOUBLE selects, LONG goes back
- Infrastructure for future: agent-suggested actions, backend orchestration calls

---

## Pillar 2: Safe Area System

### Problem
Content gets clipped by the display's rounded corners. Current `corner_mask.py` uses 8px radius cosmetically, but layout doesn't respect it — text renders into clipped zones.

### Fix
- Add `SAFE_INSET = 16` to `tokens.py`
- Update `CORNER_RADIUS` to 16 in `corner_mask.py`
- All layout math uses `SAFE_INSET`:
  - Status bar starts at `y = SAFE_INSET` (not y=0)
  - Action bar ends at `y = PHYSICAL_H - SAFE_INSET`
  - Full-screen panels (chat) inset content by `SAFE_INSET` on left/right
  - Sidebar text insets by `SAFE_INSET` from left edge
- Composite screen: vertical impact mainly (top/bottom get 16px breathing room)
- Corner mask still draws cosmetic rounded corners at `CORNER_RADIUS = 16`

### Constants
```python
SAFE_INSET = 16       # px, content margin from display edges
CORNER_RADIUS = 16    # px, cosmetic rounded corners (matches SAFE_INSET)
```

---

## Pillar 3: Action Bar (upgraded hint bar)

### Problem
Current hint bar: 12px tall, 8pt text, barely readable, text-only. Not a useful affordance.

### New design
- Rename `HintBar` → `ActionBar` (class + file)
- Height: 20px (matches status bar — balanced framing)
- Font size: `small` (10px) instead of `hint` (8px)

### Gesture icons
Three pixel-art icons rendered inline (6px each):
- `○` (circle outline) = short tap
- `◎` (double circle) = double tap
- `●` (filled circle) = hold / long press

### Format
`● RECORD  ◎ ACTIONS  ○ SCROLL` — icon + label, evenly spaced.

### API
Each screen/mode provides action bar content as a list of `(icon_type, label)` tuples:
```python
ActionBar.set_actions([
    ("hold", "RECORD"),
    ("double", "ACTIONS"),
    ("tap", "SCROLL"),
])
```

### Per-mode content (chat panel)
- IDLE: `● RECORD  ◎ ACTIONS  ○ SCROLL`
- RECORDING: `○ SEND  ● CANCEL`
- ACTIONS: `○ NEXT  ◎ SELECT  ● BACK`
- STREAMING: `listening...`
- SPEAKING: `○ STOP`

---

## Pillar 4: Typewriter Response Renderer

### Architecture
- New class `TypewriterRenderer` in `display/typewriter.py`
- Takes full response text, reveals it progressively
- Word-by-word reveal (not character-by-character — more natural for reading)

### Punctuation-aware timing
- Default: ~3 words/sec (NORMAL preset)
- After `.` `?` `!` → 400ms pause
- After `,` `:` `;` → 150ms pause
- After `\n\n` (paragraph) → 600ms pause

### Speed presets (stored in settings as `text_speed`)
| Preset | Words/sec | Setting value |
|--------|-----------|---------------|
| SLOW | 2 | `"slow"` |
| NORMAL | 3 | `"normal"` |
| FAST | 6 | `"fast"` |
| INSTANT | ∞ | `"instant"` |

### Integration
- Chat panel calls `typewriter.update(dt)` each frame
- `typewriter.get_visible_text()` returns the currently revealed portion
- Cursor blinks at end of revealed text
- When fully revealed: mode → SPEAKING (if TTS enabled) or → IDLE
- `TextSpeedPanel` in settings: cycle through presets with live preview

---

## Pillar 5: Screen Flickering Investigation

### Likely causes
1. **Backlight PWM instability** at low battery
2. **Full-surface redraw every frame** at 15 FPS without double buffering
3. **Power brownout** on Pi Zero 2W causing SPI glitches

### Sprint scope
- Investigate Wisplay board backlight pin, add stable brightness control if available
- Check if `pygame.display.flip()` vs `pygame.display.update()` matters for SPI displays
- Log battery voltage if accessible via Wisplay board API
- Add low-battery indicator in status bar (if battery API available)
- Dirty-flag rendering (only redraw when state changes) as stretch goal

---

## Out of Scope (future sprints)

### OS Rethink (next sprint)
- **Agent-driven widgets** — agent pushes widget screens (quick capture popup, task card, calendar) via `show_widget(type, data)` tool call
- **Global voice shortcut** — hold from ANY screen to start recording, not just chat
- **Menu tree system** — hierarchical navigation with breadcrumbs, back stack history
- **Second button / scroll wheel support** — dedicated scroll input, freeing tap for other actions
- **Streaming transcription** — live text appearing as you speak
- **Widget slots** — configurable home screen with swappable info cards
- **Agent gesture integration** — variable typewriter speed tied to emphasis/emotion
- **Quick capture popup** — dedicated screen that appears on gesture from anywhere

### Backend (separate track)
- API key management in settings
- MCP/tool-use wiring for smart actions
- Agent orchestration for quick action templates
- Chunked/streaming transcription API
