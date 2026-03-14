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

## P4-004 — Notification shade + panel data-source wiring

Built this sprint: settings is now wired to local persistence (web search/memory toggles, model picker, agent mode picker, sleep timer detail, and about panel), and long-press actions persist immediately where required. Notification overlay architecture is now in place via `NotificationToast` + `NotificationQueue` and is integrated into `ScreenManager` so overlays render above active screens and can consume SHORT/LONG actions first. Adapter/runtime provenance headers were also added to clarify why those integration files exist.

Read first next iteration:
1. `docs/planning/TASK_TRACKER.md`
2. `device/screens/panels/settings.py` and `device/storage/repository.py`
3. `device/overlays/notification.py` and `device/screens/manager.py`

Most important thing to know: preserve overlay-first input handling and button gesture consistency while adding real notification/settings data feeds (no keyboard-only paths).

Deliver the next Phase 4 slice:
1. Implement NotificationShade (full list view) and link overlay `on_open` flows to it.
2. Replace notifications shell placeholders with repository/provider-backed items.
3. Wire settings values that should sync with backend UI settings where applicable.
4. Extend tests for shade behavior, hydration, and error fallbacks.

### Suggested acceptance checks
- Overlay toasts continue rendering on top of any active screen with correct expiry and dismissal behavior.
- NotificationShade can open from a toast long-press and render persisted entries safely.
- Settings values survive restarts and remain consistent between detail pickers and main settings list.
- Full suite remains green with new shade/data-path coverage.

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
