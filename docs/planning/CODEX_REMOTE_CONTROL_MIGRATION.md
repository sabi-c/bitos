# Codex Remote Control Migration Plan (BITOS)

## Why this document exists

BITOS currently has multiple integration paths for remote agent control, and this has created avoidable complexity and churn. This plan defines a practical migration path to a single, proven contract: Codex App Server.

Primary goal: deliver one integrated web UI + backend path that supports approvals, streaming turns, and remote session control without custom protocol drift.

## North-star architecture

`Web UI (BITOS companion/admin) -> BITOS BFF gateway -> Codex App Server -> tool adapters (tasks/messages/email/files)`

### Design constraints
- Keep existing device runtime stable while migration happens.
- Do not block on perfect provider abstraction before shipping working remote control UX.
- Prefer protocol compatibility over bespoke endpoints.
- Preserve existing permission boundaries for write actions.

## Iteration 1 — Discovery + Architecture Lock (this sprint)

### Deliverables
1. Confirm App Server protocol fit for BITOS turn/thread + approval flows.
2. Define a minimal backend-for-frontend (BFF) API surface for the web UI.
3. Freeze provider strategy: App Server becomes default integration path.
4. Publish cutover risks and rollback.

### Acceptance criteria
- This doc committed and linked from planning surfaces.
- Task tracker has explicit Codex migration tasks.
- Handoff brief updated with execution-ready next steps.

## Iteration 2 — Vertical Slice (next sprint)

### Scope
Build a runnable vertical slice for remote control with the following features:
- create/resume session
- send prompt
- stream assistant events
- approval request/response loop
- basic connection/retry status in UI

### API sketch (BFF)
- `POST /api/codex/sessions` -> create session
- `POST /api/codex/sessions/{id}/turns` -> submit user prompt
- `GET /api/codex/sessions/{id}/events` -> stream server-sent events/websocket bridge
- `POST /api/codex/approvals/{id}` -> allow/deny

### Implementation notes
- Keep transport adapter boundary so App Server `stdio`/`websocket` can be swapped.
- Persist last N events per session for reconnect UX.
- Add explicit error classes: disconnected/auth/approval-timeout/upstream-failure.

### Acceptance criteria
- End-to-end local demo can complete one prompt + one approval flow.
- Reconnect restores visible session history.
- Focused tests pass for BFF session lifecycle and approval handling.

## Iteration 3 — Cutover + Cleanup

### Scope
- Route existing web remote-control path through BFF/App Server by default.
- Keep old path behind temporary feature flag for rollback.
- Remove dead integration code after one stable cycle.

### Acceptance criteria
- Feature flag defaults to new path.
- Old path marked deprecated and scheduled for removal.
- Tracker + handoff updated with post-cutover hardening tasks.

## Risk register

1. **Protocol mismatch with existing UI assumptions**
   - Mitigation: deliver vertical slice first, then widen.
2. **Approval UX stalls on reconnect**
   - Mitigation: persist pending approvals server-side and replay on reconnect.
3. **Adapter drift across tools**
   - Mitigation: lock one normalized tool invocation envelope at BFF boundary.
4. **Migration fatigue / partial adoption**
   - Mitigation: define feature-flagged cutover date and deprecation checklist upfront.

## Recommended immediate next actions

1. Add `server/endpoints/codex_remote.py` scaffold with placeholder routes.
2. Add `server/codex_app_client.py` adapter interface and mock transport.
3. Add `tests/test_codex_remote_endpoints.py` for session + approval happy path.
4. Ship a minimal web preview page to validate streaming and approval UX.
