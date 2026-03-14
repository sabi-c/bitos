# BITOS · ROADMAP

## Phase 1 — Voice Works
Desktop simulator + backend streaming chat baseline.

## Phase 2 — Navigation + Persistence
Lock/home flow, nav shell, SQLite persistence, settings catalog integration.

## Phase 3 — Tasks + Integrations
Adapter boundaries, outbound queue, permission gates, worker runtime loop.

## Phase 4 — Complete
Nav shell, chat, tasks, settings, focus, notifications overlay.
All tests green. P4-001 through P4-004 done.

## Phase 5 — Infrastructure + Connectivity (current)
Tailscale, firewall, BLE GATT server, companion PWA, WiFi provisioning.
Reference: docs/BLUETOOTH_NETWORK_SPEC.md + docs/planning/COMPANION_APP.md
Tasks: P5-001 (done) → P5-012f (todo)

## Phase 6 — Resilience + Reliability
5-press shutdown, offline UI, audit log, cert pinning, request signing.
Reference: docs/BACKEND_SPEC.md sections 2 and 4
Tasks: P6-001 → P6-006

## Phase 7 — Offline AI
Piper TTS, whisper.cpp STT, response cache, optional llama.cpp.
Reference: docs/planning/OFFLINE_AI.md
Tasks: P7-001 → P7-004 (P7-004 blocked until Pi 5)

## Phase 8 — AI Intelligence
Global workspace, morning brief, session distiller, agent modes, proactive notifs.
Reference: docs/BACKEND_SPEC.md section 3 (Phase 4)
Tasks: P8-001 → P8-005
Dependency: Phase 5 complete.

## Phase 9 — Companion + Extended Features
PWA companion, BLE keyboard, wake word, voice notes, conversation branching.
Reference: docs/planning/FUNCTIONALITY_ROADMAP.md
Tasks: P9-001 → P9-005

## Phase 10 — Multi-Agent Mac Service
Code/Ops/Research/Creative agent services on Mac mini.
Background tasks with device notification on completion.
Optional Electron monitor app.
Reference: docs/planning/MAC_AI_SERVICE.md
Dependency: Phase 8 (Global Workspace) must complete first.
Tasks: P10-001 → P10-008
