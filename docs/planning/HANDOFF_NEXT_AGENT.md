# BITOS Handoff Notes (Next Agent)

This document is a practical takeover brief for the next implementation contributor.

## 1) Current state snapshot

### Completed in this branch sequence
- Phase 2 shell progression: boot → lock → home flow.
- Button-first navigation in Home + reusable nav primitives (`NavItem`, `VerticalNavController`).
- Local SQLite persistence scaffold (`DeviceRepository`) with schema versioning.
- Chat session persistence + startup hydration in `ChatPanel`.
- Provider-agnostic server LLM bridge with runtime selection:
  - `anthropic`
  - `openai`
  - `openclaw`
  - `nanoclaw`
  - `echo` (deterministic local/test fallback)

### Important architectural direction
- UI/screen code should stay provider-agnostic.
- Model/runtime integration belongs behind the server bridge contract.
- Domain actions (tasks/messages/email/calendar) should be added as adapter contracts + queued execution, not direct UI calls.

---

## 2) Immediate next implementation target

## P5-010 — NetworkManager priority tuning + BT PAN baseline

Built this sprint: P5-007/008/009 filled BLE characteristic behavior for protected WiFi provisioning writes, unprotected WiFi status reads, device status read/notify updates, and protected keyboard input routing into compose targets. `ScreenManager` now exposes compose-routing helpers and pushes active-screen status updates into the device status characteristic on screen transitions. Runtime wiring in `device/main.py` now instantiates WiFi/device-status/keyboard characteristics, starts periodic device status updates, and keeps BLE paths mock-safe.

Read first next iteration:
1. `docs/planning/TASK_TRACKER.md`
2. `device/bluetooth/characteristics/wifi_config.py` and `device/bluetooth/wifi_manager.py`
3. `device/bluetooth/characteristics/device_status.py`, `device/screens/manager.py`, and `device/main.py`

Most important thing to know: preserve strict auth boundaries — `WIFI_CONFIG` and `KEYBOARD_INPUT` must continue rejecting invalid session tokens and never call their side-effect callbacks when auth fails.

Deliver the next Phase 5 slice:
1. P5-010: tune NetworkManager connection priority/fallback behavior and add BT PAN baseline.
2. Keep `BITOS_BLUETOOTH=mock` and `BITOS_WIFI=mock` paths deterministic for desktop tests.
3. Implement NOTIFICATION_RELAY characteristic only in its dedicated sprint (P5-008b), not opportunistically.
4. Keep companion protocol doc aligned with characteristic payload/schema changes.

### Suggested acceptance checks
- Protected characteristic writes fail fast on invalid session token.
- Device status notify loop starts/stops cleanly and does not block shutdown.
- Keyboard routing updates active compose field on chat and safely no-ops otherwise.
- Full `pytest -q` remains green.

---

## 3) Integration plan after P2-005

### P3 adapter baseline (recommended order)
1. Introduce domain adapter interfaces:
   - `TaskAdapter`
   - `MessageAdapter`
   - `EmailAdapter`
   - `CalendarAdapter`
2. Add local command queue with retries/dead-letter visibility.
3. Add permission/confirmation UX for write operations.
4. Keep each provider/runtime implementation behind adapter boundaries.

### Why this order
- Preserves lightweight UI iteration speed.
- Enables OpenClaw/NanoClaw/API-key providers without rewiring screens.
- Makes reliability/observability work reusable across domains.

---

## 4) Operational guidance for next agent

- Update `docs/planning/TASK_TRACKER.md` before coding and after coding.
- If scope/sequence shifts, also update:
  - `ROADMAP.md`
  - `docs/planning/IMPLEMENTATION_PLAN_NEXT.md`
- Keep commits scoped to one vertical slice when possible (easier rollback).
- Prefer adding focused tests per slice (`tests/test_*.py`) and run full discover before handoff.

---

## 5) Known implementation caveats

- `OpenAICompatibleBridge` currently performs non-streaming completion then chunks text for SSE compatibility; true upstream streaming can be added later if needed.
- Some older tracker iteration rows still use `pending` commit placeholders from historical entries; preserve history but keep new entries fully resolved.
- Keep tiny-screen constraints in mind when adding error copy (short, actionable, low-noise text).
