# BITOS

Pocket AI companion. Hold button → speak → Claude answers.
Pi Zero 2W + Whisplay HAT + PiSugar 3.

## Flash & Boot (30 min)
1. Edit `scripts/cloud-init/user-data`
   → add SSH key (`cat ~/.ssh/id_rsa.pub`)
   → add GitHub username
2. Flash SD: Pi Imager → Pi OS Lite 64-bit
3. `make flash`  ← copies cloud-init to SD
4. Insert SD, power on, wait 15 min
5. `ssh pi@bitos`
6. `bash ~/bitos/scripts/day_one.sh`  ← does everything

## Desktop Dev
```bash
cp .env.template .env  # add ANTHROPIC_API_KEY
make run-server        # terminal 1
make run-dev           # terminal 2
# SPACE=scroll ENTER=select BACKSPACE=back TAB=capture
```

## Troubleshooting
See `docs/TROUBLESHOOTING.md`.
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
- `SPACE` / `DOWN` / `J` = next (short press)
- `ENTER` = select (double press)
- `BACKSPACE` / `ESC` = back (long press)
- `UP` / `K` = previous (triple press)
- `TAB` = agent overlay

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
- `SHORT` = next item
- `DOUBLE` = select
- `LONG` = go back
- `TRIPLE` = agent overlay
- `5× PRESS` = quick menu (shutdown, reboot, settings, help)

## Current Status
- **Phase 7 in progress** — consciousness layer, voice fine-tuning, live conversation mode
- Phases 1–6 complete: hardware, display, chat, BLE, companion, resilience
- CI: passing on main
- Companion PWA: https://bitos-p8xw.onrender.com

### What's working
- Multi-turn chat with Claude (Sonnet 4.6 primary, Haiku 4.5 for sub-agents)
- 14 agent tools: iMessage, email, calendar, tasks, web search, memory, contacts, settings, approval
- 6 agent modes: Producer / Hacker / Clown / Monk / Storyteller / Director
- Long-term memory (SQLite FTS5 fact store, Haiku extraction)
- Proactive heartbeat (morning briefing, evening wind-down, idle check-in, task reminders)
- TTS with fallback chain: Cartesia → Edge TTS → Speechify → Chatterbox → Piper → OpenAI → eSpeak
- Notification system (WebSocket push, DND/priority, toast/banner rendering)
- First-boot setup wizard (5-step guided flow)
- BLE pairing + WiFi provisioning from companion app
- OTA updates via git pull

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
| `CODEX_REMOTE_CONTROL_MIGRATION.md` | Migration plan for unified Codex App Server remote-control architecture. |
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

## Mac Mini Setup (backend brain)

The Mac mini runs the AI server, task management,
and bridges to iMessage, Gmail, and calendar.

### One-command setup
```bash
git clone git@github.com:sabi-c/bitos.git
cd bitos
make setup
```

This installs:
- BITOS FastAPI server (auto-starts on login)
- Vikunja task manager (Docker, port 3456)
- Checks for BlueBubbles + Tailscale
- Prepares Pi SD cloud-init files in the same session
- Runs smoke test to confirm everything works

### After setup
Then run `make push-secrets` to point your Pi to this Mac mini.

- `make mac-status` check everything is running
- `make mac-logs` watch server logs
- `make mac-restart` apply `.env` changes

### Connecting the Pi
The Pi needs to know your Mac mini's address.
On Pi: `sudo nano /etc/bitos/secrets`
Set: `SERVER_URL=http://<tailscale-ip>:8000`

With Tailscale: `mac_setup.sh` sets this automatically.
