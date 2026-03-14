<!--
# SPRINT: P0-DOCS-3 — Complete deferred docs cleanup, expand tracker backlog, and prep handoff for P5-010/P5-011 execution.
# READS: docs/planning/TASK_TRACKER.md, docs/planning/HANDOFF_NEXT_AGENT.md, README.md, docs/planning/SECURITY_DECISIONS.md,
#        docs/planning/DEVELOPMENT_PRACTICES.md, docs/planning/FUNCTIONALITY_ROADMAP.md, docs/planning/OFFLINE_AI.md,
#        ROADMAP.md
# WRITES: docs/planning/TASK_TRACKER.md, docs/planning/SECURITY_DECISIONS.md, docs/planning/DEVELOPMENT_PRACTICES.md,
#         docs/planning/FUNCTIONALITY_ROADMAP.md, docs/planning/OFFLINE_AI.md, ROADMAP.md, README.md,
#         docs/planning/HANDOFF_NEXT_AGENT.md, device/bluetooth/network_manager.py, scripts/setup/05_network_priority.sh,
#         device/bluetooth/constants.py, device/overlays/qr_code.py, device/overlays/__init__.py, device/screens/manager.py,
#         device/main.py, device/screens/panels/settings.py, device/bluetooth/characteristics/device_info.py,
#         device/bluetooth/characteristics/__init__.py, device/bluetooth/server.py, device/bluetooth/wifi_manager.py,
#         requirements-device.txt, tests/test_network_manager.py, tests/test_qr_overlay.py, tests/test_device_info.py,
#         tests/test_settings_companion.py, tests/test_panel_shells.py
# TESTS: python scripts/validate_tracker.py, pytest -q
# DEFERRED: P5-012 companion web assets implementation (next sprint).
-->

<!--
# SPRINT: P0-DOCS-2 — Backfill missing planning/spec docs and sync tracker/handoff/readme documentation surfaces.
# READS: docs/planning/TASK_TRACKER.md, docs/planning/HANDOFF_NEXT_AGENT.md, README.md, docs/planning/SECURITY_DECISIONS.md,
#        docs/planning/DEVELOPMENT_PRACTICES.md, docs/planning/FUNCTIONALITY_ROADMAP.md, docs/planning/OFFLINE_AI.md,
#        docs/planning/MAC_AI_SERVICE.md, ROADMAP.md
# WRITES: docs/planning/TASK_TRACKER.md, docs/planning/COMPANION_APP.md, docs/planning/FIRST_BOOT.md,
#         docs/BLUETOOTH_NETWORK_SPEC.md, docs/BACKEND_SPEC.md, docs/planning/HANDOFF_NEXT_AGENT.md, README.md
# TESTS: none (documentation-only sprint)
# DEFERRED: feature/runtime code changes and any non-documentation tasks outside P0-DOCS-2.
-->

<!--
# SPRINT: P5-007/P5-008/P5-009 — Implement BLE WiFi config, device status notify, and keyboard input routing characteristics.
# READS: docs/planning/TASK_TRACKER.md, docs/planning/HANDOFF_NEXT_AGENT.md, device/bluetooth/constants.py, device/bluetooth/auth.py,
#        device/bluetooth/characteristics/wifi_config.py, device/bluetooth/characteristics/device_status.py,
#        device/screens/manager.py, device/screens/panels/chat.py, device/screens/subscreens/__init__.py,
#        README.md, ROADMAP.md
# WRITES: docs/planning/TASK_TRACKER.md, device/bluetooth/crypto.py, device/bluetooth/wifi_manager.py,
#         device/bluetooth/characteristics/wifi_config.py, device/bluetooth/characteristics/device_status.py,
#         device/bluetooth/characteristics/keyboard_input.py, device/bluetooth/characteristics/__init__.py,
#         device/bluetooth/server.py, device/main.py, device/screens/manager.py, device/screens/panels/chat.py,
#         device/screens/subscreens/__init__.py, device/bluetooth/COMPANION_PROTOCOL.md, docs/planning/MAC_AI_SERVICE.md,
#         README.md, ROADMAP.md, tests/test_wifi_config.py, tests/test_device_status.py, tests/test_keyboard_input.py,
#         tests/test_companion_protocol.py, docs/planning/HANDOFF_NEXT_AGENT.md
# TESTS: tests/test_wifi_config.py, tests/test_device_status.py, tests/test_keyboard_input.py, tests/test_companion_protocol.py
# DEFERRED: notification relay characteristic, settings/pin/reboot BLE characteristics, real desktop nmcli execution.
-->

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
| P0-AUDIT-001 | Phase 0 | Quality | Produce code-quality audit report for `device/` and `server/`, publish findings in `docs/reports/CODE_QUALITY.md` | GPT-5.2-Codex | done | 2026-03-14 | Added as todo then completed in same iteration. |
| 2026-03-14 | GPT-5.2-Codex | work | `33848ad` | Completed P5-007/P5-008/P5-009 BLE characteristics: WiFi config+status, device status notify, keyboard input routing, companion protocol doc, and Phase 10 planning docs/tasks | `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md`, `docs/planning/MAC_AI_SERVICE.md`, `README.md`, `ROADMAP.md` | Next: P5-010 NetworkManager priority tuning + BT PAN baseline |
| 2026-03-14 | GPT-5.2-Codex | work | `34cb423` | Completed P5-004/P5-005/P5-006 BLE foundation: UUID/constants, mockable GATT server shell, pairing agent, passkey overlay, BLE secret setup update, and test coverage | `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md`, `scripts/setup/02b_secrets.sh` | Next: P5-007/P5-008/P5-009 characteristic handlers (wifi config/device status/keyboard input) |
| 2026-03-14 | GPT-5.2-Codex | work | `6bdf05f` | Completed P5-001/P5-002/P5-003 infra foundation: setup scripts, remote Makefile workflows, static device-token auth middleware, and validation tests | `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md`, `scripts/setup/README.md` | Next: P5-004 BLE GATT server + transport security follow-through |
| P2-001 | Phase 2 | WS-A App Shell | Add lock screen + route from boot | GPT-5.2-Codex | done | 2026-03-14 | Implemented boot -> lock -> home flow in device runtime; added shell flow tests |
| P0-002 | Phase 0 | Planning | Publish explicit handoff brief for next contributor with immediate next slice | GPT-5.2-Codex | done | 2026-03-14 | Added `docs/planning/HANDOFF_NEXT_AGENT.md` and linked it from key docs |
| P0-AUDIT-002 | Phase 0 | Quality Audit | Run repository test coverage audit and publish prioritized coverage report | GPT-5.2-Codex | done | 2026-03-14 | Added `docs/reports/TEST_COVERAGE.md` with untested modules and priority targets |
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
| P3-006 | Phase 3 | WS-D Integrations | Run outbound worker loop from device runtime | GPT-5.2-Codex | done | 2026-03-14 | Added bounded runtime loop pump, runtime adapter wiring, and retry/dead-letter log emission in device main loop |
| P4-001 | Phase 4 | WS-E Core Screens | Build focus timer screen using shared primitives | GPT-5.2-Codex | done | 2026-03-14 | Added FocusPanel timer controls, home routing, and focused tests for transitions/countdown/back action |
| P4-002 | Phase 4 | WS-E Core Screens | Build notifications and settings screens | GPT-5.2-Codex | done | 2026-03-14 | Added Notifications/Settings shells with empty-state-safe copy, Home routing, and focused panel tests |
| P4-003 | Phase 4 | WS-E Core Screens | Settings panel real wiring + notifications overlay architecture | GPT-5.2-Codex | done | 2026-03-14 | Added persisted settings toggles/pickers/detail panels and NotificationToast/Queue overlay integration with focused tests |
| P4-004 | Phase 4 | WS-E Core Screens | Notification shade + panel data-source wiring | GPT-5.2-Codex | done | 2026-03-14 | Shipped shade overlay, notification persistence, and pull-based health/overdue poller wiring |
| P5-001 | Phase 5 | WS-F Infra & Security | Tailscale + remote access bootstrap | GPT-5.2-Codex | done | 2026-03-14 | Added idempotent setup script and remote Makefile ops shortcuts |
| P5-002 | Phase 5 | WS-F Infra & Security | Firewall + SSH hardening + secrets bootstrap | GPT-5.2-Codex | done | 2026-03-14 | Added security setup scripts and static device-token auth middleware baseline |
| P5-003 | Phase 5 | WS-F Infra & Security | System resilience + boot service setup | GPT-5.2-Codex | done | 2026-03-14 | Added resilience hardening script and systemd BITOS boot service installer |
| P5-004 | Phase 5 | WS-G Bluetooth Foundation | BLE GATT server skeleton + constants | GPT-5.2-Codex | done | 2026-03-14 | Added bluetooth module layout, UUID constants, and mockable server shell |
| P5-005 | Phase 5 | WS-G Bluetooth Foundation | LESC pairing agent baseline | GPT-5.2-Codex | done | 2026-03-14 | Added pairing agent with DisplayPasskey/RequestConfirmation and desktop mock path |
| P5-006 | Phase 5 | WS-G Bluetooth Foundation | BLE HMAC auth challenge/response | GPT-5.2-Codex | done | 2026-03-14 | Added AuthManager challenge-response, passkey overlay, setup secret generation, and runtime BLE wiring |
| P5-007 | Phase 5 | WS-G Bluetooth Foundation | WiFi config + status characteristics | GPT-5.2-Codex | done | 2026-03-14 | Implemented protected WiFi write, status characteristic, and nmcli/mock manager plumbing |
| P5-008 | Phase 5 | WS-G Bluetooth Foundation | Device status read/notify characteristic | GPT-5.2-Codex | done | 2026-03-14 | Implemented periodic updates, state-change updates on screen transitions, and notify payload serialization |
| P5-009 | Phase 5 | WS-G Bluetooth Foundation | Keyboard input routing characteristic | GPT-5.2-Codex | done | 2026-03-14 | Implemented protected keyboard writes and ScreenManager compose routing hooks |
| P5-010 | Phase 5 | WS-G Bluetooth Foundation | NetworkManager priority config + BT PAN fallback | GPT-5.2-Codex | done | 2026-03-14 | Implemented NetworkPriorityManager + nmcli setup script with WiFi priority/BT PAN baseline. |
| P5-011a | Phase 5 | WS-H Companion | Add QROverlay class + qrcode dependency | GPT-5.2-Codex | done | 2026-03-14 | Implemented QROverlay and qrcode dependency surface (with fallback-safe generation). |
| P5-011b | Phase 5 | WS-H Companion | Wire QROverlay into boot no-network flow | GPT-5.2-Codex | done | 2026-03-14 | Boot no-network flow now shows setup QR overlay and enables temporary discoverability. |
| P5-011c | Phase 5 | WS-H Companion | Wire QROverlay into Settings → Pair Companion App | GPT-5.2-Codex | done | 2026-03-14 | Settings panel now includes Companion App row and pairing QR overlay action. |
| P5-011d | Phase 5 | WS-H Companion | Add DEVICE_INFO characteristic (serial, read-only) | GPT-5.2-Codex | done | 2026-03-14 | Implemented read-only DEVICE_INFO characteristic and server wiring for companion reads. |
| P5-012a | Phase 5 | WS-H Companion | companion/setup.html — WiFi provisioning PWA | unassigned | todo | 2026-03-14 | Planned PWA setup surface |
| P5-012b | Phase 5 | WS-H Companion | companion/js/ble.js — Web Bluetooth wrapper | unassigned | todo | 2026-03-14 | Planned BLE transport wrapper |
| P5-012c | Phase 5 | WS-H Companion | companion/js/auth.js — HMAC (must match Python) | unassigned | todo | 2026-03-14 | Planned auth parity with device |
| P5-012d | Phase 5 | WS-H Companion | companion/js/crypto.js — AES-GCM encrypt | unassigned | todo | 2026-03-14 | Planned WiFi payload encryption |
| P5-012e | Phase 5 | WS-H Companion | companion/pair.html — full pairing flow | unassigned | todo | 2026-03-14 | Planned companion pairing flow |
| P5-012f | Phase 5 | WS-H Companion | Render/GitHub Pages deploy workflow | unassigned | todo | 2026-03-14 | Planned companion hosting pipeline |
| P6-001 | Phase 6 | WS-I Resilience | 5-press graceful shutdown + state save | unassigned | todo | 2026-03-14 | Planned resilience improvement |
| P6-002 | Phase 6 | WS-I Resilience | Offline mode UI states + status bar indicators | unassigned | todo | 2026-03-14 | Planned offline UX hardening |
| P6-003 | Phase 6 | WS-I Resilience | Pomodoro state persistence across reboots | unassigned | todo | 2026-03-14 | Planned continuity enhancement |
| P6-004 | Phase 6 | WS-I Resilience | Request signing on device→server calls (SD-004) | unassigned | todo | 2026-03-14 | Security alignment task |
| P6-005 | Phase 6 | WS-I Resilience | Append-only audit log for tier-2 actions (SD-006) | unassigned | todo | 2026-03-14 | Security accountability task |
| P6-006 | Phase 6 | WS-I Resilience | Anthropic API certificate pinning (SD-009) | unassigned | todo | 2026-03-14 | Security hardening task |
| P7-001 | Phase 7 | WS-J Offline AI | PiperTTS + AutoFallbackTTS bridge | unassigned | todo | 2026-03-14 | Planned offline TTS fallback |
| P7-002 | Phase 7 | WS-J Offline AI | whisper.cpp STT + AutoFallbackSTT bridge | unassigned | todo | 2026-03-14 | Planned offline STT fallback |
| P7-003 | Phase 7 | WS-J Offline AI | Response cache: store + retrieve + stale label | unassigned | todo | 2026-03-14 | Planned offline cached responses |
| P7-004 | Phase 7 | WS-J Offline AI | llama.cpp local LLM (experimental) | unassigned | blocked | 2026-03-14 | Blocked — Pi Zero 2W ~1-3 tok/s marginal. Revisit with Pi 5 (8GB). |
| P8-001 | Phase 8 | WS-K AI Core | Global workspace class + schema | unassigned | todo | 2026-03-14 | Planned shared memory foundation |
| P8-002 | Phase 8 | WS-K AI Core | Morning brief background worker (8am) | unassigned | todo | 2026-03-14 | Planned proactive summary worker |
| P8-003 | Phase 8 | WS-K AI Core | Session distiller (post-conversation) | unassigned | todo | 2026-03-14 | Planned summarization pipeline |
| P8-004 | Phase 8 | WS-K AI Core | Agent mode system prompt injection on server | unassigned | todo | 2026-03-14 | Planned server injection slice |
| P8-005 | Phase 8 | WS-K AI Core | Proactive notifications (3/day rate limit) | unassigned | todo | 2026-03-14 | Planned rate-limited proactive alerts |
| P9-001 | Phase 9 | WS-L Extensions | PWA companion app (Web Bluetooth) | unassigned | todo | 2026-03-14 | Planned companion app rollout |
| P9-002 | Phase 9 | WS-L Extensions | BLE keyboard input → device compose fields | unassigned | todo | 2026-03-14 | Planned input handoff completion |
| P9-003 | Phase 9 | WS-L Extensions | Wake word via openWakeWord (opt-in) | unassigned | todo | 2026-03-14 | Planned wake word integration |
| P9-004 | Phase 9 | WS-L Extensions | Voice notes as first-class type | unassigned | todo | 2026-03-14 | Planned voice note feature |
| P9-005 | Phase 9 | WS-L Extensions | Conversation branching (parent_message_id) | unassigned | todo | 2026-03-14 | Planned threaded branch UX |
| P10-001 | Phase 10 | WS-M MacService | Code Agent service (port 8001) + file tools | unassigned | todo | 2026-03-14 | Planned multi-agent Mac service foundation |
| P10-002 | Phase 10 | WS-M MacService | Ops Agent service (port 8003) separate process | unassigned | todo | 2026-03-14 | Planned multi-agent Mac service foundation |
| P10-003 | Phase 10 | WS-M MacService | Research Agent service (port 8002) + web tools | unassigned | todo | 2026-03-14 | Planned multi-agent Mac service foundation |
| P10-004 | Phase 10 | WS-M MacService | Creative Agent service (port 8004) | unassigned | todo | 2026-03-14 | Planned multi-agent Mac service foundation |
| P10-005 | Phase 10 | WS-M MacService | Background task queue + device notification | unassigned | todo | 2026-03-14 | Planned multi-agent Mac service foundation |
| P10-006 | Phase 10 | WS-M MacService | Background tasks screen on device | unassigned | todo | 2026-03-14 | Planned multi-agent Mac service foundation |
| P10-007 | Phase 10 | WS-M MacService | Orchestrator multi-agent routing | unassigned | todo | 2026-03-14 | Planned multi-agent Mac service foundation |
| P10-008 | Phase 10 | WS-M MacService | Electron monitor app (optional) | unassigned | todo | 2026-03-14 | Planned multi-agent Mac service foundation |
| P0-AUDIT-003 | Phase 0 | Security | Run dependency audit report for device/server requirement sets and document results | GPT-5.2-Codex | done | 2026-03-14 | Added `docs/reports/DEPENDENCY_AUDIT.md`; audit commands executed with environment limitations noted |

## Iteration Log

| Date | Contributor | Branch | Commit | Tasks completed | Docs updated | Next tasks |
|---|---|---|---|---|---|---|
| 2026-03-14 | GPT-5.2-Codex | work | `this-commit` | Completed P0-DOCS-3 + P5-010/P5-011a/b/c/d (docs cleanup, tracker expansion, network priority manager, QR overlay flows, device info characteristic, and companion settings row) | `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md`, `README.md`, `ROADMAP.md`, `docs/planning/SECURITY_DECISIONS.md`, `docs/planning/DEVELOPMENT_PRACTICES.md`, `docs/planning/FUNCTIONALITY_ROADMAP.md`, `docs/planning/OFFLINE_AI.md` | Next: P5-012a/b/c/d companion PWA files and BLE JS auth/crypto parity |
| 2026-03-14 | GPT-5.2-Codex | work | `this-commit` | Completed P0-DOCS-2 documentation audit + restoration (created missing planning/spec docs, updated README index, refreshed handoff first-read guidance) | `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md`, `README.md`, `docs/planning/COMPANION_APP.md`, `docs/planning/FIRST_BOOT.md`, `docs/BLUETOOTH_NETWORK_SPEC.md`, `docs/BACKEND_SPEC.md` | Resume P5-010 NetworkManager priority tuning + BT PAN baseline |
| 2026-03-14 | GPT-5.2-Codex | work | `dd2fd73` | Completed P4-004 notification shade + live notification sources (health state + overdue tasks), schema migration to v4, and runtime poller wiring | `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md` | P5 notification sources (Gmail/SMS), global shade gesture, notification settings |
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

| 2026-03-14 | GPT-5.2-Codex | work | `this-commit` | Implemented P3-006 runtime integration for outbound worker (bounded periodic processing, runtime adapter selection, and retry/dead-letter logging) | `device/main.py`, `device/integrations/adapters.py`, `device/integrations/runtime.py`, `device/integrations/__init__.py`, `tests/test_outbound_runtime_loop.py`, `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md` | Next: P4-001 focus timer screen using shared nav/tokens primitives |

| 2026-03-14 | GPT-5.2-Codex | work | `this-commit` | Implemented P4-001 FocusPanel (start/pause/reset/back controls), wired Home→Focus route, and added timer behavior tests | `device/screens/panels/focus.py`, `device/screens/panels/home.py`, `device/main.py`, `tests/test_focus_panel.py`, `tests/test_phase2_shell_flow.py`, `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md`, `README.md` | Next: P4-002 notifications/settings screens + simple empty/error state shells |

| 2026-03-14 | GPT-5.2-Codex | work | `this-commit` | Implemented P4-002 Notifications/Settings shell panels, wired Home routes (device + preview), and added focused panel tests | `device/screens/panels/notifications.py`, `device/screens/panels/settings.py`, `device/screens/panels/home.py`, `device/main.py`, `web_preview/server.py`, `tests/test_panel_shells.py`, `tests/test_phase2_shell_flow.py`, `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md`, `README.md` | Next: P4-003 wire real notifications/settings data flows + persistence hooks |

| 2026-03-14 | GPT-5.2-Codex | work | `this-commit` | Implemented P4-003 settings real wiring + notification overlay architecture and added focused tests | `device/storage/repository.py`, `device/screens/panels/settings.py`, `device/overlays/notification.py`, `device/overlays/__init__.py`, `device/screens/manager.py`, `device/main.py`, `web_preview/server.py`, `tests/test_settings_wiring.py`, `tests/test_notification_overlay.py`, `tests/test_panel_shells.py`, `docs/planning/TASK_TRACKER.md`, `docs/planning/HANDOFF_NEXT_AGENT.md`, `README.md` | Next: P4-004 notification shade and real notification/settings data-source integration |
