# Inline Recording UX — Chat Preview Panel

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create the implementation plan.

**Goal:** Transform the RECORD menu item in ChatPreviewPanel into a living, stateful row that handles the full voice capture lifecycle (record → transcribe → handoff) without leaving the submenu.

**Architecture:** The RECORD item becomes a state machine rendered inline. The greeting area becomes dynamically sized. The panel gains audio/STT capabilities and orchestrates the handoff to ChatPanel with pre-transcribed text.

**Tech Stack:** pygame, existing AudioPipeline + BackendClient, StepAnimator for pulsing/timing, ease_out_cubic for expansion animation.

---

## 1. Dynamic Greeting Area

The greeting header currently uses a fixed `GREETING_H = 70`. Replace with dynamic measurement.

**Behavior:**
- Minimum: 40px (1 line + padding)
- Default: 70px (2-3 lines, covers most greetings)
- Maximum: 100px (4-5 lines, agent wrote more than expected)
- Typewriter reveals text; area grows as new lines wrap
- Submenu items render at `y_offset = measured_greeting_height` instead of fixed constant
- Separator line drawn at `measured_greeting_height - 1`

**Implementation:** In `render()`, measure wrapped text height *before* rendering submenu items. Cache the measurement so it doesn't recalculate every frame unless the greeting text changes.

## 2. RECORD Row State Machine

The first menu item (`action: "respond"`) morphs through 5 states:

### State: READY (default)
- **Label:** `"RECORD"` with subtext `"Double-click to record"`
- **Icon:** `⊙⊙` prefix (double-circle suggesting double-click)
- **Behavior:** Normal PreviewPanel routing — SHORT scrolls, DOUBLE activates
- **Visual:** Standard menu row (22px), normal colors

### State: RECORDING
- **Label:** `"● REC 0:05"` — pulsing red dot + elapsed timer
- **Subtext:** `"Click to stop"`
- **Dot animation:** 2Hz sin()-based pulse between bright red (255,40,40) and dim red (140,20,20). Dot radius pulses ±1px.
- **Row background:** Subtle red tint that breathes at 1Hz (darker cycle than dot, creates layered rhythm)
- **Timer:** Counts up in `M:SS` format. Text surface only re-rendered when second changes (cached otherwise).
- **Other items:** Rendered but dimmed to DIM3, non-interactive
- **LED:** `led.recording()` (existing red breathe)
- **Gestures:** SHORT_PRESS = stop recording, DOUBLE_PRESS = also stop, LONG_PRESS = cancel (discard audio)

### State: TRANSCRIBING
- **Label:** `"TRANSCRIBING"` + animated dots (cycling `.` `..` `...` every ~267ms / 4 frames)
- **Subtext:** cleared
- **All gestures ignored** (processing)
- **LED:** `led.sending()` (existing cyan pulse)

### State: LAUNCHING
- **Label:** `"STARTING CONVERSATION..."`
- **Row expansion:** Height animates from 22px → ~50px over 5 frames (~333ms) using `ease_out_cubic`
- **Text:** Centers vertically in the growing row
- **Other items:** Pushed down by expansion (push-down model, not overlay)
- **After expansion settles (~0.5s):** Trigger handoff to ChatPanel
- **LED:** `led.success()` (existing green flash)

### State: ERROR
- **Label:** `"DIDN'T CATCH THAT"`
- **Subtext:** `"Click to retry"`
- **SHORT_PRESS:** Reset to READY, ready for another attempt
- **Auto-recovery:** If error was network, auto-retry once silently before showing error
- **Cached audio:** Keep the recorded WAV so retry doesn't require re-recording

### State transitions:
```
READY --[DOUBLE_PRESS]--> RECORDING
RECORDING --[SHORT/DOUBLE]--> (energy check) --> TRANSCRIBING or READY (silent)
RECORDING --[LONG_PRESS]--> READY (cancelled)
TRANSCRIBING --[STT success]--> LAUNCHING
TRANSCRIBING --[STT fail]--> ERROR
LAUNCHING --[expansion done]--> handoff to ChatPanel
ERROR --[SHORT_PRESS]--> RECORDING (retry with cached audio) or READY
```

## 3. Gesture Routing

`ChatPreviewPanel` overrides `handle_action()` to intercept gestures based on `_rec_state`:

- **READY:** Delegate to `super().handle_action()` (normal PreviewPanel scrolling/selection)
- **RECORDING:** SHORT/DOUBLE = stop recording. LONG = cancel. No scroll.
- **TRANSCRIBING / LAUNCHING:** All gestures swallowed (no-op)
- **ERROR:** SHORT = retry. LONG = cancel back to READY.

When `_rec_state != READY`, the base class `_render_items()` still renders all items but with a dimmed color override. The RECORD row renders its own custom content instead of the standard label.

## 4. Audio & Handoff Flow

ChatPreviewPanel needs access to `AudioPipeline` and either `BackendClient` or an STT callable. These are passed through `panel_registry.create_right_panels()`.

**Flow:**
1. DOUBLE_PRESS on RECORD → `AudioPipeline.start_recording()`
2. Recording runs until SHORT_PRESS (stop) or LONG_PRESS (cancel)
3. On stop → `AudioPipeline.stop_and_process()` returns WAV path
4. Energy check: if RMS < threshold, flash "NO AUDIO" briefly, reset to READY
5. Valid audio → state = TRANSCRIBING, send WAV to STT endpoint in background thread
6. STT returns text → state = LAUNCHING, start expansion animation
7. After expansion → `on_action("respond_with_text")` with transcribed text as payload
8. Panel registry routes to ChatPanel opener, passing transcribed text

**Threading:** Recording and STT run in background threads (same pattern as ChatPanel). State transitions are set from callbacks and checked in `update()`.

**Audio caching:** Keep last recorded WAV path in `_cached_audio_path` for retry on STT failure.

## 5. Animation Details (from research)

**Pulsing red dot (recording):**
- `sin(time * 2Hz * 2π)` mapped to 0-1 range
- Interpolate between dim red and bright red
- Radius: base 4px ± 1px with pulse
- At 15 FPS, 2Hz = ~7.5 frames per cycle — smooth enough

**Row expansion (launching):**
- `ease_out_cubic(t) = 1 - (1 - t)^3` — front-loads 70% of motion into first half
- 5 frames at 15 FPS = 333ms total
- Height: 22px → 50px (28px growth)
- Items below pushed down by `current_h - 22` pixels

**Animated dots (transcribing):**
- Cycle through `""`, `"."`, `".."`, `"..."` every 4 frames (~267ms)
- Append to pre-rendered "TRANSCRIBING" text surface

**Pre-rendering:** Cache text surfaces for each state. Only re-render recording timer when second changes. Pre-render "TRANSCRIBING", "STARTING CONVERSATION..." etc. at init.

## 6. Future Iterations (Out of Scope)

- Full-screen recording takeover with waveform visualization
- Audio start/stop tones (ascending/descending pips, <150ms)
- Haptic feedback via vibration motor
- Border color encoding state (red=recording, blue=processing, green=responding)
- Inline two-way conversation without leaving preview panel
- Dynamic bullet-point agent responses in greeting area
- Sprite sheet icons replacing text labels
- Hold-progress bar connecting button to screen
- Dither-mask transitions between screens

## 7. Research References

Key findings from 4 parallel research agents:

**Dynamic UI (row animations):**
- ease_out_cubic is optimal at 15 FPS — most motion in first 2-3 frames
- Pre-render text surfaces, only re-render timer on second change
- Avoid alpha blending on Pi Zero 2W — simulate by color interpolation
- TE-style hard cut + 1-frame flash is viable fallback if animation stutters

**Voice UX:**
- Tap-to-toggle is best for single-button (not PTT or VAD-only)
- 500ms minimum recording length to filter accidental taps
- Cache recorded audio for retry without re-recording
- Border color conventions: red=recording, blue=processing, green=done

**Power management:**
- WiFi power_save + disable HDMI/BT = biggest wins (40-90mA saved)
- Adaptive FPS (30→10→1 based on activity) saves 30-80mA
- OLED black pixels = zero power (dark UI is a power feature)
- schedutil CPU governor best for responsive + power-aware

**UI polish:**
- 2Hz pulse = ~7.5 frames/cycle at 15 FPS (smooth enough)
- Pre-rendered dither masks enable cheap fade transitions
- Breathing separators / status dot heartbeat for ambient life
- Pebble icon angles (45, 26.57, 18.43 degrees) for pixel-perfect rendering
