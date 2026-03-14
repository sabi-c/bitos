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

## P5-012a — Companion PWA `setup.html` baseline

Built this sprint: all audit follow-up fixes are complete, including UI render-path cache cleanup, SD trace-comment coverage across security boundaries, and WiFi timeout hardening + regression tests for timeout paths.

Read first next iteration:
1. `docs/planning/TASK_TRACKER.md`
2. `companion/setup.html`
3. `companion/` assets + scripts referenced by setup flow

Most important thing to know: audit remediations are now complete; preserve those invariants while starting companion onboarding UI work.

Deliver the next Phase 5 slice:
1. P5-012a: scaffold companion PWA `setup.html` baseline flow.
2. Keep companion work isolated to `companion/` assets with no device/server regressions.
3. Preserve existing BLE protocol contracts and docs while adding setup UX.
4. Add focused companion tests/checks where available.

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
