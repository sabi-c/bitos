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
| P0-002 | Phase 0 | Planning | Publish explicit handoff brief for next contributor with immediate next slice | GPT-5.2-Codex | done | 2026-03-14 | Added `docs/planning/HANDOFF_NEXT_AGENT.md` and linked it from key docs |
| P2-002 | Phase 2 | WS-A App Shell | Implement sidebar navigation for button-only controls | GPT-5.2-Codex | done | 2026-03-14 | Added focusable home nav items + button/keyboard navigation tests |
| P2-002b | Phase 2 | WS-A App Shell | Extract reusable nav controller/item model for future pages | GPT-5.2-Codex | done | 2026-03-14 | Added `VerticalNavController` + `NavItem` and coverage tests for wrap/activation behavior |
| P2-003 | Phase 2 | WS-B Persistence | Add SQLite schema + migration runner (`sessions/messages/settings/events`) | GPT-5.2-Codex | done | 2026-03-14 | Added `DeviceRepository` with schema versioning + startup migration initialization and tests |
| P2-004 | Phase 2 | WS-B Persistence | Persist and hydrate chat sessions at startup | GPT-5.2-Codex | done | 2026-03-14 | ChatPanel now restores latest session and persists user/assistant turns to SQLite |
| P2-005 | Phase 2 | WS-C Reliability | Add backend connectivity banner + retry UX in chat | GPT-5.2-Codex | done | 2026-03-14 | Added status banner states, normalized client errors, and retry affordances with tests |
| P2-006 | Phase 2 | WS-B Persistence | Add backend-driven UI settings catalog + persisted theme/layout controls | GPT-5.2-Codex | done | 2026-03-14 | Added `/settings/catalog`, `/settings/ui` GET/PUT, device consumption, and tests |
| P3-001 | Phase 3 | WS-D Integrations | Define task provider adapter contract | GPT-5.2-Codex | done | 2026-03-14 | Added protocol contracts + normalized adapter result for task/message/email/calendar domains |
| P3-003 | Phase 3 | WS-D Integrations | Add provider-agnostic LLM bridge for Anthropic/OpenAI/OpenClaw/NanoClaw | GPT-5.2-Codex | done | 2026-03-14 | Added bridge abstraction + config-driven provider selection and API tests |
| P3-002 | Phase 3 | WS-D Integrations | Implement local outbound queue with retry/dead-letter | GPT-5.2-Codex | done | 2026-03-14 | Added SQLite-backed queue states/retry/dead-letter metrics with focused reliability tests |
| P3-004 | Phase 3 | WS-D Integrations | Add permission gate UX + queue worker wiring for outbound commands | GPT-5.2-Codex | done | 2026-03-14 | Added confirmation-gated enqueue service + adapter-driven queue worker with retry/dead-letter tests |
| P3-005 | Phase 3 | WS-D Integrations | Surface queue/dead-letter status in device debug UI | GPT-5.2-Codex | done | 2026-03-14 | ChatPanel now shows compact queue/dead-letter status + latest reason with test coverage |
| P3-006 | Phase 3 | WS-D Integrations | Run outbound worker loop from device runtime | unassigned | todo | 2026-03-14 | Drain queue periodically and map adapter outcomes to retry/dead-letter transitions |
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
| 2026-03-14 | GPT-5.2-Codex | work | `aa73e91` | Implemented P2-002 button-only sidebar behavior with focus movement + item activation semantics | `device/screens/panels/home.py`, `tests/test_phase2_shell_flow.py`, `docs/planning/TASK_TRACKER.md` | Start P2-003 SQLite schema + migration runner |

| 2026-03-14 | GPT-5.2-Codex | work | `pending` | Hardened Phase 2 navigation by extracting reusable menu primitives and wiring HomePanel to shared controller | `device/screens/components/nav.py`, `device/screens/components/__init__.py`, `device/screens/panels/home.py`, `tests/test_nav_controller.py`, `docs/planning/TASK_TRACKER.md`, `docs/planning/IMPLEMENTATION_PLAN_NEXT.md` | Continue P2-003 SQLite schema + migration runner implementation |

| 2026-03-14 | GPT-5.2-Codex | work | `c83cf42` | Implemented Phase 2 local persistence and hydration groundwork (schema migrations + chat session restore) | `device/storage/repository.py`, `device/storage/__init__.py`, `device/screens/panels/chat.py`, `device/main.py`, `web_preview/server.py`, `tests/test_device_repository.py`, `tests/test_chat_persistence.py`, `.env.template`, `README.md`, `docs/planning/IMPLEMENTATION_PLAN_NEXT.md`, `docs/planning/TASK_TRACKER.md` | Continue P2-005 reliability UX (connectivity banner + retry controls) |

| 2026-03-14 | GPT-5.2-Codex | work | `b7ae192` | Added provider-agnostic LLM bridge architecture/docs and backend runtime abstraction for Anthropic/OpenAI/OpenClaw/NanoClaw | `server/llm_bridge.py`, `server/main.py`, `server/config.py`, `tests/test_llm_bridge.py`, `tests/test_server_chat_bridge_api.py`, `README.md`, `ROADMAP.md`, `docs/planning/IMPLEMENTATION_PLAN_NEXT.md`, `.env.template`, `docs/planning/TASK_TRACKER.md` | Continue P2-005 reliability UX and then P3 adapter expansion for task/message/email/calendar domains |

| 2026-03-14 | GPT-5.2-Codex | work | `b4768ee` | Published handoff packet for next agent with prioritized next steps (P2-005) and integration guidance | `docs/planning/HANDOFF_NEXT_AGENT.md`, `README.md`, `ROADMAP.md`, `docs/planning/IMPLEMENTATION_PLAN_NEXT.md`, `docs/planning/TASK_TRACKER.md` | Next contributor implements P2-005 reliability UX slice |

| 2026-03-14 | GPT-5.2-Codex | work | `0232e1a` | Linked handoff brief in README docs index for discoverability | `README.md` | Next contributor starts from handoff brief and executes P2-005 |

| 2026-03-14 | GPT-5.2-Codex | work | `this-commit` | Implemented P2-005 reliability UX in chat (status banner, normalized errors, retry controls, outage-safe behavior) | `device/client/api.py`, `device/screens/panels/chat.py`, `tests/test_chat_reliability.py`, `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md` | Start P3-001 adapter interfaces and P3-002 outbound queue baseline |
| 2026-03-14 | GPT-5.2-Codex | work | `this-commit` | Implemented P3-001/P3-002 integration foundation (adapter contracts + durable outbound queue with retries/dead-letters + metrics) | `device/integrations/contracts.py`, `device/integrations/queue.py`, `device/storage/repository.py`, `tests/test_adapter_contracts.py`, `tests/test_outbound_queue.py`, `docs/adr/0001-adapter-and-queue-baseline.md`, `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md` | Next: P3-004 permission/confirmation UX for write operations + worker loop wiring |

| 2026-03-14 | GPT-5.2-Codex | work | `this-commit` | Implemented P3-004 permission gate + worker wiring (confirmed enqueue service and adapter-driven queue processor) | `device/integrations/permissions.py`, `device/integrations/worker.py`, `device/integrations/__init__.py`, `tests/test_outbound_permissions.py`, `tests/test_outbound_worker.py`, `tests/test_device_repository.py`, `docs/adr/0002-permission-gate-and-queue-worker.md`, `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md` | Next: P3-005 queue status visibility in device debug surface |

| 2026-03-14 | GPT-5.2-Codex | work | `this-commit` | Implemented P3-005 queue/dead-letter debug visibility in ChatPanel and validated with focused tests | `device/screens/panels/chat.py`, `tests/test_chat_queue_status.py`, `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md` | Next: P3-006 worker loop integration in runtime + adapter wiring |
