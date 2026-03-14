# BITOS Roadmap

This roadmap turns the original phase sketch into a delivery sequence with explicit outcomes and gates.

## North Star

Ship a dependable pocket AI companion where voice interaction, navigation, and core daily workflows are fast on-device and resilient when backend services are degraded.

## Phase 1 — Voice Works (current baseline)

**Outcome:** Desktop simulator + backend streaming chat is functional end-to-end.

- Pygame device loop, boot animation, chat panel
- FastAPI `/health` and `/chat` streaming endpoint
- Web preview server (MJPEG)
- Baseline project scaffolding and local run commands

**Exit criteria**
- `make dev-server`, `make dev-device`, and `make dev-preview` run locally
- Message send + streamed assistant output visible in chat panel

## Phase 2 — Navigation + Persistence

**Outcome:** Device feels like a multi-screen product instead of a single chat view.

- Lock screen + sidebar navigation shell
- Persistent local SQLite store (chat sessions, settings, recent activity)
- Backend settings catalog + UI theming controls (`/settings/catalog`, `/settings/ui`)
- Session restore at boot
- Error states for backend unavailable / timeout
- Provider-agnostic LLM bridge (Anthropic/OpenAI/OpenClaw/NanoClaw)

**Exit criteria**
- Boot lands on lock/home flow
- Navigation can reach all implemented screens with button-only controls
- Chat history survives restart
- Active LLM provider can be swapped via config without UI changes
- UI settings changes are persisted and reflected in device/preview runtime

## Phase 3 — Tasks + MCP Foundations

**Outcome:** First utility workflow beyond chat, with external integration boundaries in place.

- Task capture + task list panel
- Integration adapter boundary for Things (or pluggable task provider)
- Local queue + retry for outbound sync
- Permission/confirmation UX for external actions
- OS bridge adapters for tasks/messages/email/calendar with provider-independent contracts

**Exit criteria**
- User can capture, browse, and complete tasks on-device
- Sync failures are visible and recoverable
- Domain adapter boundaries allow local/runtime-specific implementations without screen-layer edits

## Phase 4 — Core Screen Set

**Outcome:** Core information architecture is implemented.

- Focus timer view
- Mail summary view
- Settings and notifications screens
- Shared UI primitives across screens

**Exit criteria**
- All priority screens accessible and visually consistent
- Screen-level smoke tests pass

## Phase 5 — Hardware Deployment

**Outcome:** Same UX runs on Pi Zero 2W + Whisplay HAT + PiSugar.

- ST7789 display driver implementation
- WM8960 audio pipeline integration (record, STT, TTS playback)
- Device startup/service supervision (systemd)
- Hardware diagnostics mode

**Exit criteria**
- Physical button, display, and audio path function reliably
- Device auto-starts app after reboot

## Phase 6 — Global Workspace Intelligence

**Outcome:** Contextual memory and proactive summaries become useful.

- Shared memory model for sessions/events
- Morning brief + proactive suggestions
- Retrieval boundaries and privacy policy enforcement

**Exit criteria**
- Daily brief generated from local + integrated data
- Context retrieval improves response quality without notable latency regressions

## Phase 7 — Companion App

**Outcome:** Onboarding and remote interaction are simple for non-technical users.

- iOS/macOS companion app for Wi-Fi setup and device config
- Optional keyboard relay and remote prompt handoff
- Device management surface (status, logs, updates)

**Exit criteria**
- Fresh device can be provisioned without shell access
- Remote controls are authenticated and encrypted


## Execution hygiene (required each iteration)

- Update `docs/planning/TASK_TRACKER.md` before and after each iteration.
- Record per-iteration progress in the tracker's **Iteration Log** (who, commit, what changed, what's next).
- Keep roadmap and implementation docs synchronized when scope/sequence changes.
- PRs should map changes to at least one tracker task ID.
- Maintain/update `docs/planning/HANDOFF_NEXT_AGENT.md` when transitions between contributors are expected.

## Cross-phase quality bars

- Startup time and UI responsiveness budgets are tracked each phase
- Fallback UX exists for network/API outages
- Feature flags for unfinished capabilities on default branch
- Every phase ships with a manual QA checklist and at least one automated smoke test path


## Phase 10 — Multi-Agent Mac Service

Code/Ops/Research/Creative agent services running as separate
processes on Mac mini. Background task queue with device
notification on completion. Optional Electron monitor.
Reference: docs/planning/MAC_AI_SERVICE.md
Dependency: Phase 8 (Global Workspace) must complete first.
Tasks: P10-001 through P10-008

