# BITOS Handoff Notes (Next Agent)

This document is a practical takeover brief for the next implementation contributor.

## 1) Current state snapshot

BITOS has broad feature coverage but too many remote-control integration paths. The current priority is to converge on a single implementation contract for web-based control.

### Completed in this iteration
- Added `docs/planning/CODEX_REMOTE_CONTROL_MIGRATION.md` with a 3-iteration cutover plan.
- Updated planning surfaces to include Codex remote-control migration as active architecture direction.
- Added explicit Phase 11 guidance to implementation plan.

### Important architectural direction (effective now)
- Codex App Server path is the default direction for remote control.
- BITOS should expose a BFF gateway that normalizes session/turn/events/approvals.
- Legacy remote-control paths are maintenance-only until cutover.

---

## 2) Immediate next implementation target

### CODEX-UI-003 — Real transport integration

Deliver this next:
1. Keep endpoint contract in `server/endpoints/codex_remote.py` stable (`/api/codex/...`).
2. Add a real transport-backed client (App Server stdio first, websocket optional) behind `server/codex_app_client.py` interface.
3. Add configuration switch between mock and real transport for safe rollout.
4. Extend tests with transport-level failure cases (disconnect, timeout, invalid approval replay).

### Suggested acceptance checks
- `pytest -q tests/test_codex_remote_endpoints.py`
- add focused tests for transport failure and reconnect handling

---

## 3) Operational guidance for next agent

- Update `docs/planning/TASK_TRACKER.md` status transitions before and after coding.
- If cutover sequencing shifts, update both:
  - `ROADMAP.md`
  - `docs/planning/IMPLEMENTATION_PLAN_NEXT.md`
- Keep commits scoped: one vertical slice per commit where possible.
- Favor deterministic mock transport tests before wiring real App Server transport.
