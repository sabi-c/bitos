# BITOS Detailed Implementation Plan (Next Iteration)

This document expands the existing Phase 1 scaffold plan into an execution-ready plan for Phases 2–4, including workstreams, sequencing, acceptance criteria, and risks.


## 0) Iteration Tracking Protocol (required)

Use `docs/planning/TASK_TRACKER.md` as the single source of truth for in-flight and completed work.

Per iteration (agent or human):
- Claim/update task IDs in **Active Backlog** before coding.
- Update status + notes inline while working (`todo` → `in_progress` → `done`/`blocked`).
- Add an **Iteration Log** entry with commit hash and follow-up tasks.
- If priorities or sequencing changed, patch this plan and `ROADMAP.md` in the same PR.

## 1) Current-State Review

Based on the current repository:

- Device simulator loop, boot flow, and chat panel are implemented.
- Backend health and streaming chat endpoint are implemented.
- Web preview service exists for mobile-browser testing.
- Planning docs currently emphasize scaffold setup more than delivery sequencing.

## 2) Planning Assumptions

- Primary target remains Pi Zero 2W hardware; desktop simulator is the fastest iteration loop.
- Phase 2 should prioritize navigation + persistence to reduce rework in every subsequent screen.
- Phase 3 should establish integration boundaries (adapters, queues, retries) before broad feature expansion.
- Phase 4 should finish core UX breadth using shared primitives created in Phase 2.

## 3) Workstreams

### WS-A: App Shell & Navigation

**Goal:** Move from single-screen app to predictable multi-screen shell.

Deliverables:
- Global app state object (active screen, modal state, transient notifications).
- Sidebar/navigation model supporting button-only interaction.
- Lock/home entry flow.

Definition of done:
- User can navigate across implemented screens with no keyboard requirement.
- Returning to chat preserves in-progress composition state.

### WS-B: Persistence & Data Model

**Goal:** Persist user context and app state safely.

Deliverables:
- SQLite schema (`sessions`, `messages`, `settings`, `events`).
- Data access layer with migration/versioning support.
- Startup hydration and periodic flush policies.

Definition of done:
- Restarting the device restores latest active session + settings.
- Migration path from schema v1 to v2 tested with fixture DB.

### WS-C: Reliability & Error Handling

**Goal:** Handle degraded backend/API states gracefully.

Deliverables:
- Unified error types for timeout, auth, and upstream failures.
- UI status banners and retry affordances.
- Exponential backoff policy for non-interactive retries.

Definition of done:
- Offline mode presents clear state and does not crash the render loop.
- Failed chat attempts are retryable from UI.

### WS-D: Integration Foundation (Tasks/MCP)

**Goal:** Add first external workflow without coupling UI to provider implementation.

Deliverables:
- Provider adapter interface for task operations.
- Local command queue with retry and dead-letter tracking.
- Permission gate UX for write actions.

Definition of done:
- Switching provider implementation does not require UI-layer edits.
- Failed sync action remains visible and user-resolvable.

### WS-E: UX Breadth (Core Screens)

**Goal:** Ship a coherent set of daily-use screens.

Deliverables:
- Focus, mail summary, settings, notifications screens.
- Shared components (header, list row, status chip, toast).
- Screen-level loading/empty/error states.

Definition of done:
- All screens share typography/spacing tokens and transition behavior.
- Screen smoke tests cover render + one interaction path.

## 4) Sequenced Milestones (6 Weeks)

## Milestone 1 (Week 1): Shell Foundations

- Introduce app shell state model and nav map.
- Add lock screen and route transitions from boot.
- Refactor `ScreenManager` for route-based transitions.

Acceptance criteria:
- Boot → lock/home flow works on desktop and preview modes.
- Navigation latency stays under one frame (<=33ms target at 30 FPS).

## Milestone 2 (Week 2): Persistence Core

- Add SQLite schema and migration runner.
- Persist messages and settings; hydrate on startup.
- Add repository abstraction used by chat panel.

Acceptance criteria:
- App restart restores previous conversation and selected settings.
- Migration test verifies upgrade from empty DB and seeded v1 DB.

## Milestone 3 (Week 3): Reliability Pass

- Normalize backend/client exceptions.
- Add UI-visible connectivity state and retry controls.
- Add integration tests for `/chat` timeout/error handling.

Acceptance criteria:
- Simulated backend downtime does not crash app.
- User can recover via retry without restart.

## Milestone 4 (Week 4): Tasks/MCP Foundations

- Implement task domain model + local queue.
- Add provider adapter interface with mock provider.
- Build minimal task panel (capture/list/complete).

Acceptance criteria:
- Task actions function locally with eventual sync semantics.
- Queue state is inspectable in debug logs.

## Milestone 5 (Week 5): Core Screens

- Add focus, mail summary, notifications, settings screens.
- Introduce reusable components and state patterns.
- Add keyboard parity for simulator-only shortcuts.

Acceptance criteria:
- All new screens reachable via sidebar.
- Empty/loading/error states implemented for each screen.

## Milestone 6 (Week 6): Stabilization & Release Gate

- Run cross-screen QA and performance sweeps.
- Finalize docs/runbooks and operational checklists.
- Tag release candidate for hardware phase handoff.

Acceptance criteria:
- Smoke test suite passes in CI.
- Known issues triaged with severity + owner + timeline.

## 5) Recommended Backlog Structure

Use epics + vertical slices:

- EPIC-01 App shell
- EPIC-02 Persistence
- EPIC-03 Reliability
- EPIC-04 Tasks integration
- EPIC-05 Core screens
- EPIC-06 Stabilization

Each story should include:
- user-facing behavior
- technical scope boundary
- instrumentation/logging requirement
- explicit acceptance test command(s)
- task tracker linkage (`Task ID: P2-00x`)

## 6) Test Strategy Upgrades

- Add unit tests for:
  - button gesture timing edge cases
  - text wrapping and viewport clipping
  - repository CRUD and migrations
- Add API tests for `/health` and `/chat` stream framing.
- Add integration smoke test script:
  1) start backend
  2) run simulated chat exchange
  3) assert non-empty streamed chunks

## 7) Delivery Risks and Mitigations

1. **Threading/render race conditions in chat streaming**  
   Mitigation: confine UI state mutation to main thread via queue-drain in `update()`.

2. **Schema churn without migrations discipline**  
   Mitigation: enforce migration files and schema version checks in startup path.

3. **UI complexity growth from screen proliferation**  
   Mitigation: require shared component usage and enforce token-only styling.

4. **Hardware divergence late in project**  
   Mitigation: keep display/input abstractions strict and run periodic headless integration checks.

## 8) Decision Log (Proposed)

Create a lightweight ADR folder (`docs/adr/`) and capture decisions for:
- persistence schema conventions
- navigation state machine
- provider adapter contract
- retry/backoff semantics

A single paragraph per decision is enough, but document the trade-off and fallback.
