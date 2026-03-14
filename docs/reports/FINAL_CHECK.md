# FINAL PRE-HARDWARE CHECK
Date: 2026-03-14

## Test Suite
Result: 206 passed, 0 failed, 0 skipped
Status: PASS

## Import Chain
device.main: OK
server.main: OK

## Makefile Targets
- run-dev: OK
- run-server: OK
- run-both: OK
- run-pi: OK
- verify-hw: OK
- deploy: OK
- ship: OK

## Critical Files
- scripts/install.sh: OK
- scripts/verify_hardware.py: OK
- scripts/smoke_test.py: OK
- scripts/validate_tracker.py: OK
- scripts/cloud-init/user-data: OK
- scripts/setup/01_tailscale.sh: OK
- scripts/setup/02_security.sh: OK
- scripts/setup/02b_secrets.sh: OK
- scripts/setup/03_resilience.sh: OK
- scripts/setup/04_bitos_service.sh: OK
- scripts/setup/05_network_priority.sh: OK
- scripts/setup/06_offline_ai.sh: OK
- device/assets/fonts/PressStart2P.ttf: OK
- companion/setup.html: OK
- companion/pair.html: OK
- companion/js/ble.js: OK
- companion/js/auth.js: OK
- companion/js/crypto.js: OK
- docs/planning/FIRST_BOOT.md: OK
- docs/planning/HANDOFF_NEXT_AGENT.md: OK
- docs/reports/UI_SPEC_GAPS.md: OK
- docs/reports/BOOT_READINESS.md: OK
- .env.template: OK
- .github/workflows/ci.yml: OK

## Env Template
Missing keys: none

## Companion URL
constants.py: https://bitos-p8xw.onrender.com
.env.template: https://bitos-p8xw.onrender.com
Match: YES

## Task Tracker
Validation: PASS
Done: 54  Todo: 34  Blocked: 1

## VERDICT
READY FOR HARDWARE

## SHIP-PREP-001 audit results (2026-03-14)
- Pi-specific code paths: all 7 env branches (DISPLAY, AUDIO, BUTTON, BLUETOOTH, BATTERY, WIFI, ADAPTER_MODE) have complete Pi implementations
- Voice loop: fixed blocking capture (now threaded with 5s record window), added stop_recording() sequencing, added TTS playback after LLM response
- Vikunja adapter: `server/integrations/vikunja_adapter.py` with mock-mode fallback, wired into agent_modes system prompt
- Boot sequence: status messages now differentiate first-boot, no-API-key, online, offline
- main.py bugs fixed: undefined `surface` in render loop, missing `PowerOverlay` import, duplicate logger, `print()` replaced with `logger`

## Fixes applied previous sprint
- Added missing critical report file: `docs/reports/UI_SPEC_GAPS.md`.
- Added missing `.env.template` key: `BITOS_BATTERY`.
- Corrected malformed `.env.template` companion URL entry (`BITOS_COMPANION_URL`).
