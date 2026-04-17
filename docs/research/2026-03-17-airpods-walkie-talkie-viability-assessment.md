# AirPods Walkie-Talkie Mode — System Gap Assessment (BITOS)

**Date:** 2026-03-17  
**Goal:** Hands-free-ish relay mode with AirPods gestures:
- Tap once to start recording
- Tap again to stop + send to agent
- Hear response in AirPods
- Repeat without staring at phone/app UI

---

## Executive Readout

**Viability now:**
- **V1 (tap-to-record/tap-to-send/reply audio): HIGH**
- **V2 (full gesture matrix + head gestures + deep OS-level control): MEDIUM**

**Why:** Core audio/chat infrastructure already exists. Biggest unresolved piece is **AirPods gesture ingestion + mapping reliability** across device/OS combinations.

---

## 1) Current Capability Snapshot (what is already shipped)

### A. Voice relay primitives are present
- Audio pipeline supports record, stop, transcribe, and speak.
- Chat preview already has a recording state machine (`READY → RECORDING → TRANSCRIBING → LAUNCHING`).

**Implication:** Walkie-talkie behavior is mostly a control/input integration task, not a full rebuild.

### B. Bluetooth audio plumbing exists
- Bluetooth audio manager already scans, pairs, and connects A2DP-capable devices.
- This is sufficient to route response audio to AirPods-class headphones.

### C. Gesture abstraction exists for single-button UX
- Button input is normalized into semantic events (`SHORT`, `DOUBLE`, `LONG`, `TRIPLE`, `HOLD_START`, `HOLD_END`).

**Implication:** Add an AirPods input source that emits semantic actions into the same event pipeline.

### D. Prior research foundation exists
- Existing internal docs already mapped AVRCP routes (BlueZ DBus first, evdev fallback).

---

## 2) Gap Analysis (what is missing right now)

| Gap | Current State | Impact | Priority |
|---|---|---|---|
| AirPods event listener in runtime | Missing | Cannot trigger record/send from AirPods gestures | P0 |
| Gesture-to-action mapping config | Missing | Hard to adapt across AirPods models/user preference | P0 |
| Input arbitration (button + AirPods + UI) | Partial | Race/conflicts during record/speak transitions | P1 |
| Diagnostics for BT/gesture health | Minimal | Hard to debug reliability in field | P1 |
| Head gesture support (nod/shake) | Missing | No V2 “full gesture” experience yet | P2 |
| Scroll-wheel integration path | Concept only | No expansion input path for navigation mode | P2 |

---

## 3) Option Matrix (including your GBIOS / VTOS direction)

> Working interpretation for planning:
> - **GBIOS track** = on-device firmware/runtime path (direct hardware + BT events)
> - **VTOS track** = voice transport/orchestration path (session, turn-taking, optional realtime framework)

### Option 1 — **GBIOS-first (recommended for immediate product value)**
- Implement AirPods event ingestion directly in device runtime.
- Map Play/Pause to record-toggle (start / stop+send).
- Keep existing server and UI architecture.

**Pros:** Fastest path, least risk, uses shipped code.  
**Cons:** Gesture quality depends on BlueZ+device specifics.

### Option 2 — **VTOS-first (service-oriented voice control layer)**
- Introduce dedicated voice-session orchestrator (stateful relay service).
- Device sends normalized input events; VTOS decides turn boundaries and actions.

**Pros:** Cleaner long-term architecture, easier multi-client behavior.  
**Cons:** More infra and latency tuning before user-visible win.

### Option 3 — **Hybrid (GBIOS V1 → VTOS V2)**
- Ship GBIOS gesture bridge now.
- Migrate advanced turn-taking and interruption policy to VTOS later.

**Pros:** Best balance of speed + future proofing.  
**Cons:** Requires clean interface boundary from day one.

---

## 4) Recommended Product Scope

### V1 (ship first)
1. AirPods connected to BITOS over Bluetooth audio.
2. Single gesture path: `Play/Pause` toggles record state.
3. Stop action sends to agent automatically.
4. Agent reply plays in AirPods.
5. Add confidence tones + tiny status indicator.

### V1.5
- Optional mapping for next/previous/volume gestures.
- Add per-user configurable mappings.
- Add reliability dashboard/log panel.

### V2
- Head gestures (if API-supported on target platform).
- Full interruption policy (barge-in quality improvements).
- Optional VTOS orchestration layer / LiveKit-Pipecat exploration.
- Scroll wheel integration as secondary input mode (navigation + scrub + volume).

---

## 5) Key Risks and Mitigations

### Risk: inconsistent gesture event delivery across stack
**Mitigation:** DBus primary + evdev fallback + health checks + user remapping.

### Risk: long-press/advanced AirPods gestures not externally exposed
**Mitigation:** Do not depend on long-press for V1 core flow.

### Risk: input collisions (button vs AirPods vs active panel)
**Mitigation:** Explicit input-priority state machine in voice mode.

### Risk: iOS “global while locked” expectations
**Mitigation:** Keep V1 anchored to BITOS device-hosted path, not phone OS privileges.

---

## 6) Decision

**Proceed with Hybrid strategy:**
1. **Now:** GBIOS-first AirPods bridge for walkie-talkie loop.
2. **Next:** Define VTOS boundary once gesture relay is stable and adopted.

This gets you real-world usage quickly while preserving a clear path to richer capabilities.

---

## 7) Immediate Build Checklist (next sprint)

1. Add `device/input/airpods.py` event monitor (DBus + fallback).
2. Add mapping table (`settings`-driven) from AirPods events to semantic actions.
3. Route semantic actions into current recording/chat state machine.
4. Add basic observability: last gesture, last send, active sink, capture state.
5. Add tests for record-toggle sequencing and error fallback.

---

## Bottom line

You already have most of the platform needed. The shortest path is to **treat AirPods gestures as another input source feeding the existing walkie-talkie flow**, then evolve toward VTOS/head-gesture/scroll-wheel sophistication in staged releases.
