# BITOS
Pocket AI device for daily planning and voice interaction, built for Raspberry Pi Zero 2W + Whisplay HAT + PiSugar 3.

## What it does
Hold the button, speak, and Claude answers through the speaker.
The UI is 1-bit pixel-style on a 240×280 display with single-button navigation.

## Quick Start (desktop dev)
1. `git clone <repo-url> && cd bitos`
2. `cp .env.template .env` and add `ANTHROPIC_API_KEY`
3. `pip install -r requirements.txt`
4. `make run-server` (terminal 1)
5. `make run-dev` (terminal 2)

Keyboard mapping in desktop mode:
- `SPACE` = short
- `ENTER` = long
- `BACKSPACE` = back
- `TAB` = quick-capture

## First Boot on Hardware
See `docs/planning/FIRST_BOOT.md`.

Short version:
1. Flash SD card.
2. Copy cloud-init: `scripts/cloud-init/user-data`.
3. Power on and wait ~15 minutes.
4. `ssh pi@bitos`
5. Add API key.
6. `sudo systemctl start bitos`

## Architecture
`Device (Pygame/ST7789) → HTTP → Server (FastAPI) → Claude API`

Single button model:
- `SHORT` = scroll
- `LONG` = select
- `DOUBLE` = back
- `TRIPLE` = capture

## Current Status
- Phase 5 complete (BLE foundation, WiFi provisioning, companion PWA)
- Phase 6 in progress (resilience, shutdown, offline UI)
- CI: passing on main
- Companion PWA: https://bitos-p8xw.onrender.com

## Companion App
Scan the device QR code to open the companion in Safari (iPhone) or Chrome (Mac/Android).
It provisions WiFi over BLE when the device has no network.

## Development
Three environments:

| Environment | Key env values |
|---|---|
| DESKTOP | `BITOS_DISPLAY=pygame`, `BITOS_AUDIO=mock`, `BITOS_BUTTON=keyboard` |
| PI-DEV | `BITOS_DISPLAY=st7789`, `BITOS_AUDIO=hw:0`, `BITOS_BUTTON=gpio` |
| PI-PROD | same as PI-DEV |

Useful commands:
- `make run-dev` — desktop simulator
- `make run-server` — FastAPI backend
- `make run-both` — run both
- `make verify-hw` — hardware check (run on Pi)
- `make deploy` — push code to Pi
- `make ship` — deploy + restart + logs

## Docs
### Planning docs (`docs/planning/`)

| File | Purpose |
|---|---|
| `AGENT_DOCS_SPRINT_PROMPT.md` | Agent sprint prompt template and workflow notes. |
| `COMPANION_APP.md` | Companion PWA scope, behavior, and acceptance criteria. |
| `DEVELOPMENT_PRACTICES.md` | Coding and development norms. |
| `FIRST_BOOT.md` | First-boot checklist and bring-up flow. |
| `FUNCTIONALITY_ROADMAP.md` | Product-surface roadmap details by capability. |
| `HANDOFF_NEXT_AGENT.md` | Immediate next-agent execution handoff. |
| `IMPLEMENTATION_PLAN_NEXT.md` | Sequenced execution plan for current phases. |
| `MAC_AI_SERVICE.md` | Phase 10 multi-agent Mac service plan. |
| `OFFLINE_AI.md` | Offline AI strategy (Piper/whisper.cpp/llama.cpp). |
| `SECURITY_DECISIONS.md` | Security decision log (SD-001 through SD-010). |
| `TASK_TRACKER.md` | Canonical backlog and iteration log. |

### Spec and reference docs (`docs/`)

| File | Purpose |
|---|---|
| `BACKEND_SPEC.md` | Server API and runtime behavior contract. |
| `BLUETOOTH_NETWORK_SPEC.md` | BLE + WiFi provisioning protocol contract. |
| `reports/` | Audits and readiness reports (quality, dependencies, boot, architecture). |
| `adr/` | Architecture decision records for major design choices. |
| `reference-ui/README.md` | UI reference source location conventions. |

## Agent Modes
Producer / Hacker / Clown / Monk / Storyteller / Director.
Set in **Settings → Agent Mode**. Modes change Claude personality and context.
Live task list + battery status are injected into prompts.

## Security
Security decisions are documented in `docs/planning/SECURITY_DECISIONS.md` (SD-001 through SD-010).
