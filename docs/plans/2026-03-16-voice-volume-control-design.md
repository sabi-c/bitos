# Voice & Volume Control System Design

**Date:** 2026-03-16
**Status:** Approved

## Overview

Design for voice/volume controls, speaking overlay, thinking animation, text display polish, and settings integration for the BITOS device (Pi Zero 2W, 240x280 OLED, WM8960 audio HAT).

## 1. Speaking Overlay

When TTS is playing, a small overlay strip appears at the bottom of the screen (above the footer):
- Shows a small speaker/waveform icon + "speaking..." text
- 24-28px strip, similar to existing toast style
- Gesture overrides while active:
  - SHORT press → stop speaking, dismiss overlay, return to chat
  - HOLD → stop speaking, start recording a reply
- Auto-dismisses when TTS finishes

While response is streaming:
- SHORT press → skip to showing whatever text has arrived so far (impatient tap)

## 2. Voice & Volume Settings

Three layers of control:

### Agent-side (inline commands, already working):
- `{{volume:NUMBER}}` — agent sets volume 0-100
- `{{voice:on/off}}` — agent toggles voice

### User-side (settings panel):
- **Voice mode**: Off / On / Auto (three-way toggle)
  - Off — never speak, agent commands ignored
  - On — always speak responses
  - Auto — agent decides (default when API key is set)
- **Volume**: step control 0-100, increments of 10
- **Voice selection**: pick TTS voice (future expansion)
- **Test Voice**: button that synthesizes a short phrase and plays it with loading states

### Priority logic:
- User setting always wins. If user sets Off, agent's {{voice:on}} is ignored
- Auto means agent's inline commands are respected
- response_format_hint tells agent the current mode so it doesn't try to enable voice when user has it forced off

## 3. Thinking Animation

When user sends a message:
1. User's message appears immediately as formatted text
2. Below it, a thinking indicator with rotating phrases:
   - Pool: "thinking", "pondering", "wondering", "considering", "reflecting", "looking up at the stars"
   - Each phrase types out letter-by-letter, then dots animate: . → .. → ...
   - After ~3-4 seconds, clear and type out next phrase
   - Cycle until response arrives
3. Optional filler audio: preloaded local WAV clips ("hmm", thinking sound) play on message send when voice is enabled. 3-4 variants, randomized.

## 4. Buffered Pagination (Text Display Polish)

No streaming text visible to user. Pages appear clean and formatted:

1. User sends message → thinking animation plays
2. Response chunks buffer invisibly in background
3. Once enough text for page 1 (~250 chars), thinking stops, page 1 appears fully formatted
4. User navigates to page 2 — if ready, shows. If not, brief "..." until content arrives
5. TTS starts on first sentence as soon as available (sentence-by-sentence synthesis)
6. Markdown rendering (bold, italic, code, headers, bullets) applied per page
7. No visible reflow or jumping — each page built once with enough content

## 5. TTS Test in Settings

- Remove auto-boot TTS test from main.py
- Add "Test Voice" option in settings panel
- When triggered, shows step-by-step loading:
  - "connecting..." → "synthesizing..." → "playing..." → "done" (or error detail)
- Uses existing tts_test.py functions under the hood

## 6. Heartbeat Audio Gating

- Proactive messages (greeting, heartbeat, task reminders) do NOT auto-trigger TTS
- TTS only fires when:
  - User is in an active chat session AND
  - Voice mode is On, or Auto with agent enabling it
- Notification banners remain visual-only
- If user responds to a banner via hold-to-speak, that conversation can have voice if enabled

## Implementation Order

Iterative sprints, deployable after each:

1. **Sprint 1**: Speaking overlay + gesture controls + heartbeat audio gating
2. **Sprint 2**: Voice settings (Off/On/Auto) + volume in settings + Test Voice button
3. **Sprint 3**: Thinking animation with rotating phrases
4. **Sprint 4**: Buffered pagination (no streaming text visible)
5. **Sprint 5**: Sentence-by-sentence TTS streaming + filler audio
6. **Sprint 6**: Voice selection UI + response_format_hint updates
