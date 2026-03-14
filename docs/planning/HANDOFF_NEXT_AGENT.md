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

## P3-006 — Runtime worker loop integration + adapter wiring

P3-005 baseline is now complete:
- ChatPanel now renders compact queue/dead-letter status (`q:<depth> d:<count>`) on-device.
- Latest dead-letter reason is surfaced in short tiny-screen-safe copy.
- Added focused tests for queue status copy with/without repository wiring.

Deliver the next Phase 3 slice:
1. Run `OutboundCommandWorker.process_once()` periodically from device runtime loop.
2. Wire runtime-selected adapters into worker construction (mock/echo adapter allowed initially).
3. Keep worker processing non-blocking and bounded per frame/tick.
4. Emit concise logs when commands move to retrying or dead-letter states.

### Suggested acceptance checks
- Enqueued command is processed without manual trigger when runtime loop is active.
- Retryable worker failures transition to retrying and later succeed when adapter recovers.
- Dead-letter count increments on non-retryable failures and appears in chat debug status.
- Existing tests remain green and new runtime-loop tests are added.

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
