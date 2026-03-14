# BITOS Task Tracker

This file is the canonical task management surface for the repository.

## How every agent/contributor should use this file

For **every implementation iteration** (code or docs):

1. Add or update tasks in **Active Backlog** before starting.
2. During work, update task status and notes in-line.
3. On completion, append an entry to **Iteration Log** with:
   - date
   - contributor/agent
   - branch + commit
   - tasks completed
   - docs updated
   - next tasks
4. If work changes phase scope, also update `ROADMAP.md` and `docs/planning/IMPLEMENTATION_PLAN_NEXT.md` in the same PR.

## Status legend

- `todo` — ready to start
- `in_progress` — actively being worked
- `blocked` — needs dependency/decision
- `done` — shipped to default branch

## Active Backlog

| ID | Phase | Workstream | Task | Owner | Status | Updated | Notes |
|---|---|---|---|---|---|---|---|
| P2-001 | Phase 2 | WS-A App Shell | Add lock screen + route from boot | GPT-5.2-Codex | done | 2026-03-14 | Implemented boot -> lock -> home flow in device runtime; added shell flow tests |
| P2-002 | Phase 2 | WS-A App Shell | Implement sidebar navigation for button-only controls | unassigned | todo | 2026-03-14 | Define focused item behavior |
| P2-003 | Phase 2 | WS-B Persistence | Add SQLite schema + migration runner (`sessions/messages/settings/events`) | unassigned | todo | 2026-03-14 | Add schema version table |
| P2-004 | Phase 2 | WS-B Persistence | Persist and hydrate chat sessions at startup | unassigned | todo | 2026-03-14 | Requires P2-003 |
| P2-005 | Phase 2 | WS-C Reliability | Add backend connectivity banner + retry UX in chat | unassigned | todo | 2026-03-14 | Define retry backoff policy |
| P2-006 | Phase 2 | WS-B Persistence | Add backend-driven UI settings catalog + persisted theme/layout controls | GPT-5.2-Codex | done | 2026-03-14 | Added `/settings/catalog`, `/settings/ui` GET/PUT, device consumption, and tests |
| 2026-03-14 | GPT-5.2-Codex | work | `pending` | Added backend UI settings catalog/persistence + device runtime theming hooks + API tests | `server/main.py`, `server/ui_settings.py`, `server/config.py`, `device/display/theme.py`, `device/client/api.py`, `device/main.py`, `device/screens/panels/chat.py`, `device/screens/lock.py`, `device/screens/panels/home.py`, `web_preview/server.py`, `tests/test_ui_settings_store.py`, `tests/test_server_settings_api.py`, `tests/test_device_theme.py`, `.env.template`, `README.md`, `ROADMAP.md`, `docs/planning/IMPLEMENTATION_PLAN_NEXT.md`, `docs/reference-ui/README.md`, `docs/planning/TASK_TRACKER.md` | Start P2-002 and render setting/editing controls in-app after HTML refs sync |
| P3-001 | Phase 3 | WS-D Integrations | Define task provider adapter contract | unassigned | todo | 2026-03-14 | Keep UI/provider decoupled |
| P3-002 | Phase 3 | WS-D Integrations | Implement local outbound queue with retry/dead-letter | unassigned | todo | 2026-03-14 | Queue visibility in logs |
| P4-001 | Phase 4 | WS-E Core Screens | Build focus timer screen using shared primitives | unassigned | todo | 2026-03-14 | Reuse tokens and transitions |
| P4-002 | Phase 4 | WS-E Core Screens | Build notifications and settings screens | unassigned | todo | 2026-03-14 | Include empty/error states |

## Iteration Log

| Date | Contributor | Branch | Commit | Tasks completed | Docs updated | Next tasks |
|---|---|---|---|---|---|---|
| 2026-03-14 | GPT-5.2-Codex | work | `b07c5ae` | Added in-repo roadmap and detailed implementation plan docs | `README.md`, `ROADMAP.md`, `docs/planning/IMPLEMENTATION_PLAN_NEXT.md` | Establish explicit task tracking policy and seed backlog |
| 2026-03-14 | GPT-5.2-Codex | work | `d4fd9cc` | Established canonical task tracker + contributor iteration protocol | `docs/planning/TASK_TRACKER.md`, roadmap/plan/readme updates | Start P2-001 and P2-003 in next implementation PR |
| 2026-03-14 | GPT-5.2-Codex | work | `5e21327` | Repository-wide artifact audit for missing UI references; added asset-recovery backlog item P0-001 | `docs/planning/TASK_TRACKER.md` | Locate source of HTML prototypes and commit them under `docs/reference-ui/` |
| 2026-03-14 | GPT-5.2-Codex | work | `pending` | Created canonical reference-ui docs location + import naming conventions | `README.md`, `docs/reference-ui/README.md`, `docs/planning/TASK_TRACKER.md` | Add synced HTML artifacts under `docs/reference-ui/` and mark P0-001 done |
| 2026-03-14 | GPT-5.2-Codex | work | `pending` | Implemented first Phase 2 shell slice (boot->lock->home) and action routing groundwork | `device/main.py`, `device/screens/base.py`, `device/screens/manager.py`, `device/screens/lock.py`, `device/screens/panels/home.py`, `tests/test_phase2_shell_flow.py`, `docs/planning/TASK_TRACKER.md` | Start P2-002 (button-only sidebar navigation) using HTML reference screens as source |
