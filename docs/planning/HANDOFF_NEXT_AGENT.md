# BITOS Handoff Notes (Next Agent)

This document is a practical takeover brief for the next implementation contributor.

## 1) Current state snapshot

Pre-hardware sprints complete. Device arriving today.
Next: hardware bring-up via FIRST_BOOT.md.
Run scripts/verify_hardware.py first on Pi.


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


### Documentation sweep completed (P0-DOCS-2)
- Audited markdown footprint (`docs/`, `scripts/`, repo root) and confirmed missing docs were restored.
- Added committed planning/spec docs:
  - `docs/planning/COMPANION_APP.md`
  - `docs/planning/FIRST_BOOT.md`
  - `docs/BLUETOOTH_NETWORK_SPEC.md`
  - `docs/BACKEND_SPEC.md`
- Updated README docs index to include the new planning/spec references.

## P5-012 — Companion PWA implementation slices

Built this sprint: completed P0-DOCS-3 plus P5-010/P5-011a/b/c/d. Added NetworkManager priority helper + setup script, QR overlay infrastructure, boot no-network QR setup flow, Settings→Companion App QR pairing row, and read-only `DEVICE_INFO` BLE characteristic wiring. Docs/roadmap/tracker were synchronized with expanded P5-P10 backlog and explicit security/development plans.

Read first next iteration:
1. `docs/planning/TASK_TRACKER.md`
2. `docs/BLUETOOTH_NETWORK_SPEC.md` and `docs/planning/COMPANION_APP.md`
3. `device/overlays/qr_code.py`, `device/bluetooth/network_manager.py`, and `device/main.py`

Most important thing to know: preserve strict auth boundaries and schema parity — keep `WIFI_CONFIG`/`KEYBOARD_INPUT` protected by session tokens, and ensure upcoming companion JS HMAC/AES implementations match Python exactly before enabling real provisioning writes.

Deliver the next Phase 5 slice:
1. Implement P5-012a/b/c/d companion web assets (`setup.html`, BLE/auth/crypto JS parity).
2. Keep `BITOS_BLUETOOTH=mock` and `BITOS_WIFI=mock` paths deterministic for desktop tests.
3. Maintain QR flow compatibility with `BITOS_COMPANION_URL` and URL versioning (`v=1`).
4. Keep companion protocol docs aligned with payload/schema changes.

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
