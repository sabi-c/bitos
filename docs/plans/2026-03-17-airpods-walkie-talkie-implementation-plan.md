# AirPods Walkie-Talkie Mode — Implementation Plan (GBIOS → VTOS)

**Date:** 2026-03-17  
**Planning horizon:** 2–4 sprints  
**Primary outcome:** Reliable tap-to-record / tap-to-send / spoken-reply loop using AirPods on BITOS.

---

## 1) Architecture Target

## In-scope V1 control loop
`AirPods Gesture -> AirPodsInputHandler -> ActionMapper -> Recording State Machine -> STT -> Agent -> TTS -> AirPods`

### New modules to add
- `device/input/airpods.py`
  - BlueZ DBus listener (primary)
  - evdev fallback listener
  - emits normalized event enum
- `device/input/action_mapper.py`
  - user-configurable mapping from raw gesture events to semantic actions
- `device/input/input_router.py` (or integrate existing handler)
  - resolves conflicts between button and AirPods actions

### Suggested event enum
- `AIRPOD_PLAY_PAUSE`
- `AIRPOD_NEXT`
- `AIRPOD_PREVIOUS`
- `AIRPOD_VOLUME_UP`
- `AIRPOD_VOLUME_DOWN`
- `AIRPOD_UNKNOWN`

---

## 2) Phased Delivery

## Phase 0 — Baseline validation (0.5 sprint)
- Verify AirPods connect/disconnect reliability in target environment.
- Capture and log actual events from your specific AirPods model.
- Confirm playback sink routing behavior under reconnect.

**Exit criteria:** deterministic event visibility + stable output routing.

## Phase 1 — V1 walkie-talkie control (1 sprint)
- Implement Play/Pause -> record toggle behavior.
- If currently recording: stop + send.
- If idle: start recording.
- Add short confirmation cue for state transitions.

**Exit criteria:** 50+ consecutive successful relay cycles in bench test.

## Phase 2 — Hardening and operator UX (1 sprint)
- Add diagnostics panel (connection, last gesture, state, errors).
- Add debounce/cooldown and duplicate-event protection.
- Add fallback path to physical button at all times.

**Exit criteria:** robust behavior under reconnects/noise/rapid taps.

## Phase 3 — Expansion (optional)
- Add gesture remapping UI/settings.
- Add scroll-wheel compatibility layer.
- Define VTOS interface for advanced turn-taking/interruptions.

**Exit criteria:** configurable controls + clear migration boundary.

---

## 3) Initial Mapping Spec

| AirPods Event | Semantic Action | Default Behavior |
|---|---|---|
| Play/Pause | `TOGGLE_RECORD_SEND` | Start recording if idle; else stop + send |
| Next | `NAV_NEXT` | Optional: next item / quick mode action |
| Previous | `NAV_PREV` | Optional: previous item / back context |
| VolumeUp | `VOLUME_UP` | +10 volume |
| VolumeDown | `VOLUME_DOWN` | -10 volume |

**V1 requirement:** only Play/Pause mapping is mandatory.

---

## 4) Reliability Rules (must-have)

1. **Debounce window:** ignore duplicate gesture within 150–250 ms.
2. **State lock:** during `TRANSCRIBING`/`LAUNCHING`, ignore non-critical nav gestures.
3. **Safety fallback:** if AirPods input stream fails, button control remains authoritative.
4. **Reconnection reset:** clear transient gesture states on BT disconnect.
5. **Telemetry:** log event timestamp, action, current state, result.

---

## 5) Testing Plan

## Unit tests
- Mapper tests: raw event -> semantic action
- Router tests: collision handling between button/AirPods
- State tests: idle->recording->send transitions

## Integration tests
- Simulated event stream for rapid taps, duplicates, disconnects
- Ensure no stuck recording on reconnect
- Ensure TTS still routes to connected sink after send cycle

## Field tests
- 30-minute walking scenario
- AirPods in/out ear transitions
- BT reconnect across temporary signal loss

---

## 6) Definition of Done (V1)

- Single tap gesture reliably toggles record/send loop.
- Agent response is consistently heard in AirPods.
- Failure states are visible and recoverable.
- Physical button fallback always works.
- Basic diagnostics available for debugging.

---

## 7) VTOS Readiness Boundary (for later)

When these conditions are met, VTOS becomes worth it:
1. V1 is stable with real usage.
2. You need richer interruption/turn-taking policies.
3. You need multi-client/multi-input orchestration.

At that point, keep device gesture capture in GBIOS and move turn policy into VTOS.
