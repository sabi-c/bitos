# AGENT PROMPT — DOCUMENTATION + PLANNING SPRINT
# Paste baseline prompt first, then this

YOUR TASK: P0-DOCS — Ingest new planning documents, update 
TASK_TRACKER and README to reflect full project scope

━━━ CONTEXT ━━━
Four new planning documents have been added to docs/planning/:

  SECURITY_DECISIONS.md       — append-only security decision log (SD-001 through SD-010)
  DEVELOPMENT_PRACTICES.md    — codified engineering practices
  FUNCTIONALITY_ROADMAP.md    — all post-v1 features with phases and effort estimates
  OFFLINE_AI.md               — offline capability stack (piper TTS → llama.cpp)

Also added to docs/:
  BLUETOOTH_NETWORK_SPEC.md   — BLE GATT architecture, WiFi boot flow, network security
  BACKEND_SPEC.md             — backend architecture, permission model, phase build plan

This sprint is DOCUMENTATION ONLY. No new feature code.
Your job: read all six documents, then update the project files
below so the repo reflects the full picture of what's been planned.

━━━ PART 1: READ EVERYTHING FIRST ━━━

Before writing a single line, read these files in order:
  docs/planning/SECURITY_DECISIONS.md
  docs/planning/DEVELOPMENT_PRACTICES.md
  docs/planning/FUNCTIONALITY_ROADMAP.md
  docs/planning/OFFLINE_AI.md
  docs/BLUETOOTH_NETWORK_SPEC.md
  docs/BACKEND_SPEC.md
  docs/planning/TASK_TRACKER.md        ← existing tasks
  README.md                            ← existing readme

━━━ PART 2: UPDATE TASK_TRACKER.md ━━━

Add the following new tasks. Do not modify existing rows.

Phase 5 — Infrastructure + Connectivity:
  P5-001  WS-F DevOps     Install + configure Tailscale + Tailscale SSH on Pi  todo
  P5-002  WS-F DevOps     Configure ufw firewall + fail2ban + SSH hardening (SD-008)  todo
  P5-003  WS-F DevOps     Install log2ram + hardware watchdog + systemd MemoryMax  todo
  P5-004  WS-G Bluetooth  Implement BlueZ GATT server skeleton + UUID constants (SD-007)  todo
  P5-005  WS-G Bluetooth  Implement LESC passkey pairing agent (SD-001)  todo
  P5-006  WS-G Bluetooth  Implement AUTH_CHALLENGE/RESPONSE handshake (SD-002)  todo
  P5-007  WS-G Bluetooth  Implement WIFI_CONFIG characteristic write (SD-003)  todo
  P5-008  WS-G Bluetooth  Implement DEVICE_STATUS + NOTIFICATION_RELAY notify  todo
  P5-009  WS-G Bluetooth  Implement KEYBOARD_INPUT → active compose field routing  todo
  P5-010  WS-G Bluetooth  NetworkManager priority config + BT PAN fallback  todo
  P5-011  WS-H Companion  Write companion protocol spec (iOS CoreBluetooth GATT client contract)  todo
  P5-012  WS-H Companion  Evaluate PWA (Web Bluetooth) vs native iOS vs Shortcuts  todo

Phase 6 — Resilience + Reliability:
  P6-001  WS-I Resilience 5-press graceful shutdown with in-flight state save  todo
  P6-002  WS-I Resilience Offline mode UI states + status bar indicators  todo
  P6-003  WS-I Resilience Pomodoro state persistence across reboots  todo
  P6-004  WS-I Resilience Request signing on device→server calls (SD-004)  todo
  P6-005  WS-I Resilience Append-only audit log for tier-2 actions (SD-006)  todo
  P6-006  WS-I Resilience Anthropic API certificate pinning (SD-009)  todo

Phase 7 — Offline AI:
  P7-001  WS-J OfflineAI  Implement PiperTTS + AutoFallbackTTS bridge  todo
  P7-002  WS-J OfflineAI  Implement WhisperCppSTT + AutoFallbackSTT bridge  todo
  P7-003  WS-J OfflineAI  Response cache: store + retrieve + stale labeling  todo
  P7-004  WS-J OfflineAI  Llama.cpp local LLM (experimental, Pi Zero 2W)  blocked

Phase 8 — AI Intelligence:
  P8-001  WS-K AICore     Global workspace class + today/background/recent schema  todo
  P8-002  WS-K AICore     Morning brief background worker (8am cron)  todo
  P8-003  WS-K AICore     Session distiller (runs after conversation ends)  todo
  P8-004  WS-K AICore     Agent mode system prompt injection on server  todo
  P8-005  WS-K AICore     Proactive notification sources (3/day rate limit)  todo

Phase 9 — Companion + Extended Features:
  P9-001  WS-L Companion  PWA companion app (Web Bluetooth, WiFi config)  todo
  P9-002  WS-L Companion  BLE keyboard input → device compose fields  todo
  P9-003  WS-L Voice      Wake word via openWakeWord (opt-in)  todo
  P9-004  WS-L Voice      Voice notes as first-class type  todo
  P9-005  WS-L Voice      Conversation branching (parent_message_id in schema)  todo

Add P7-004 with status "blocked" and note: "Requires Pi 5 (8GB) 
for practical performance. Pi Zero 2W marginal at ~1-3 tok/s."

━━━ PART 3: ADD ROADMAP.md PHASE SECTIONS ━━━

If ROADMAP.md exists, add or update these phase descriptions:

Phase 5 — Infrastructure + Connectivity
  Tailscale remote access, firewall hardening, BLE GATT server,
  companion app protocol, WiFi boot provisioning flow.
  Reference: docs/BLUETOOTH_NETWORK_SPEC.md

Phase 6 — Resilience + Reliability  
  5-press graceful shutdown, offline mode UI, audit logging,
  certificate pinning, request signing.
  Reference: docs/BACKEND_SPEC.md sections 2 and 4.

Phase 7 — Offline AI
  Piper TTS fallback, Whisper.cpp local STT, response cache,
  optional Llama.cpp local LLM (experimental).
  Reference: docs/planning/OFFLINE_AI.md

Phase 8 — AI Intelligence
  Global workspace, morning brief, session distiller, agent modes,
  proactive notifications.
  Reference: docs/BACKEND_SPEC.md section 3 (Phase 4).

Phase 9 — Companion + Extended Features
  PWA companion app, BLE keyboard, wake word, voice notes,
  conversation branching.
  Reference: docs/planning/FUNCTIONALITY_ROADMAP.md

━━━ PART 4: UPDATE README.md ━━━

Update the docs index section (or create one if missing) to list:

  docs/planning/TASK_TRACKER.md          — canonical task list
  docs/planning/HANDOFF_NEXT_AGENT.md    — current sprint handoff
  docs/planning/IMPLEMENTATION_PLAN_NEXT.md — phase detail
  docs/planning/SECURITY_DECISIONS.md   — NEW: security decision log
  docs/planning/DEVELOPMENT_PRACTICES.md — NEW: engineering practices
  docs/planning/FUNCTIONALITY_ROADMAP.md — NEW: full feature roadmap
  docs/planning/OFFLINE_AI.md           — NEW: offline capability plan
  docs/BLUETOOTH_NETWORK_SPEC.md        — NEW: BLE + network security
  docs/BACKEND_SPEC.md                  — NEW: backend architecture

Update the "Current Phase" section to show:
  PHASE 4 IN PROGRESS (P4-004 next)
  PHASES 5-9 PLANNED — see FUNCTIONALITY_ROADMAP.md

Add a "Security" section to README pointing to SECURITY_DECISIONS.md.

Add a "Development Setup" section referencing DEVELOPMENT_PRACTICES.md
with the three environment targets (DESKTOP / PI-DEV / PI-PROD).

━━━ PART 5: UPDATE HANDOFF ━━━

Update docs/planning/HANDOFF_NEXT_AGENT.md:
  - Note that P0-DOCS sprint added 6 planning documents
  - Next agent reads P4-004 prompt (notification shade + live sources)
  - Key constraint: notifications are overlays, not screens
  - Point to FUNCTIONALITY_ROADMAP.md for full picture of where 
    this is all going

━━━ TESTS ━━━

No code tests for this sprint.
Verify docs are internally consistent:
  - Every task ID in TASK_TRACKER.md has a unique ID
  - No duplicate IDs
  - All new P5-P9 tasks have status "todo" (except P7-004: "blocked")
  - All phase numbers in ROADMAP.md match TASK_TRACKER.md

Write a simple Python validation script:
  scripts/validate_tracker.py
  
  Reads TASK_TRACKER.md, parses the table, asserts:
  - No duplicate task IDs
  - All statuses are valid (todo/in_progress/blocked/done)
  - All phases are valid strings
  
  Run with: python scripts/validate_tracker.py
  Exit 0 = valid. Exit 1 = errors printed to stdout.

━━━ COMMIT STRUCTURE ━━━

Commit 1: Add docs/planning/ new documents (SECURITY_DECISIONS, 
           DEVELOPMENT_PRACTICES, FUNCTIONALITY_ROADMAP, OFFLINE_AI)
Commit 2: Add docs/ new documents (BLUETOOTH_NETWORK_SPEC, BACKEND_SPEC)
           (these may already exist — verify before creating)
Commit 3: Update TASK_TRACKER.md with P5-P9 tasks
Commit 4: Update ROADMAP.md with new phases
Commit 5: Update README.md with docs index + phase status
Commit 6: Update HANDOFF_NEXT_AGENT.md
Commit 7: Add scripts/validate_tracker.py
