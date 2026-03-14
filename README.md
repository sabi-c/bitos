# BITOS

![CI](https://github.com/sabi-c/bitos/actions/workflows/ci.yml/badge.svg)

A pocket AI companion device. Pi Zero 2W + Whisplay HAT + PiSugar 3.

Hold the button, ask Claude something, hear it answer.

## Quick Start

```bash
# 1. git clone + cd
git clone git@github.com:sabi-c/bitos.git
cd bitos

# 2. cp .env.template .env, then edit ANTHROPIC_API_KEY
cp .env.template .env

# 3. install dependencies
pip install -r requirements.txt

# 4. terminal 1
make run-server

# 5. terminal 2
make run-dev
```

That's it — Pygame window opens, SPACE/ENTER/BACKSPACE to navigate.

## Architecture

## Current Delivery Status

- Phase 4 shell set is complete (lock/home/chat/settings/focus/notifications overlay).
- BLE foundation slices `P5-007`, `P5-008`, and `P5-009` are done (WiFi config/status, device status notify, keyboard routing).
- Next up: `P5-010` NetworkManager priority + BT PAN baseline and `P5-011` QR companion pairing flow.

```
Device (Pygame/ST7789) ──HTTP──▶ Server (FastAPI) ──▶ Claude API
```

- **Device:** 240×280 pixel display, 1-bit monochrome aesthetic, single button input
- **Server:** FastAPI backend, streams Claude responses via SSE
- **Web Preview:** MJPEG stream for testing on mobile browsers

## UI Settings Catalog (Backend-driven)

BITOS now exposes backend-managed UI settings so theming/layout adjustments are cataloged and reproducible:

```bash
# Fetch editable settings schema/catalog
curl http://localhost:8000/settings/catalog

# Fetch current effective settings
curl http://localhost:8000/settings/ui

# Update one or more settings
curl -X PUT http://localhost:8000/settings/ui \
  -H "Content-Type: application/json" \
  -d '{"font_scale": 1.15, "layout_density": "compact"}'

# Verify required HTML reference pages exist before UI porting
make audit-reference-ui
```

Settings persistence path defaults to `server/data/ui_settings.json` and can be overridden with `UI_SETTINGS_FILE`.


## Local Persistence (SQLite)

The device runtime now initializes a local SQLite database for sessions/messages/settings/events.

- Default path: `device/data/bitos.db`
- Override with: `BITOS_DB_FILE`
- Migration/version tracking is handled automatically at startup

## LLM Bridge (Provider-agnostic)

BITOS now treats chat generation as a provider bridge instead of a single hardcoded backend model.

- Configure provider via `LLM_PROVIDER` (`anthropic`, `openai`, `openclaw`, `nanoclaw`, `echo`)
- Anthropic uses `ANTHROPIC_API_KEY` + `MODEL_NAME`
- OpenAI/OpenClaw/NanoClaw use OpenAI-compatible `/chat/completions` settings (`*_API_KEY`, `*_BASE_URL`, `*_MODEL`)
- Shared prompt can be tuned with `BITOS_SYSTEM_PROMPT`

This keeps the device/UI layer unchanged while swapping model providers or self-hosted agent runtimes.

## OS Bridge Direction (Tasks/Messages/Email/Calendar)

The architecture direction is to keep UI and providers decoupled via adapters and queues:

1. LLM bridge for prompt/response generation (this phase)
2. Domain adapters for task/message/email/calendar actions (next phases)
3. Local command queue + retries + permission gates for external writes

This allows routing to API-key providers or local agent runtimes (OpenClaw/NanoClaw) without rewriting screens.

### Outbound Worker Runtime (Phase 3)

The device loop now runs a bounded outbound worker pump each frame cadence to process queued task/message/email/calendar actions without blocking render/input.

- Adapter mode is configurable via `BITOS_ADAPTER_MODE`:
  - `echo` (default): local deterministic success adapter for simulator/dev
  - `disabled`: intentionally unavailable adapter to exercise retry/dead-letter behavior
- Queue transitions to `retrying` and `dead_letter` emit concise runtime logs for observability.

## Extending Navigation

For button-first menu screens, use the shared navigation primitives in `device/screens/components/nav.py`:

- `NavItem` defines label/status/enablement/action
- `VerticalNavController` handles focus movement + activation

This keeps new pages lightweight: define items, render rows, and map selected actions to screen transitions.

Phase 4 started with a `FocusPanel` timer shell wired from Home (`FOCUS`) using the same navigation primitives and tiny-screen copy constraints. NotificationsPanel and SettingsPanel routes are wired from Home (`NOTIFS`, `SETTINGS`), and Settings is now persistence-wired (toggles + model/agent/sleep/about detail screens). NotificationToast overlay infrastructure is also integrated in `ScreenManager` for above-screen transient alerts.

## Next Handoff Package

If handing implementation to a new contributor/agent, start here:

- `docs/planning/HANDOFF_NEXT_AGENT.md` — current state + immediate execution plan for the next iteration
- `docs/planning/TASK_TRACKER.md` — canonical backlog/status updates
- `docs/planning/IMPLEMENTATION_PLAN_NEXT.md` — sequencing and acceptance criteria

## Docs

| Document | Purpose |
|---|---|
| docs/planning/MAC_AI_SERVICE.md | Multi-agent Mac service + collab-electron pattern |
| docs/planning/COMPANION_APP.md | Companion app scope, security expectations, and MVP acceptance criteria |
| docs/planning/FIRST_BOOT.md | First-boot provisioning flow, state machine, and failure handling |
| docs/BLUETOOTH_NETWORK_SPEC.md | BLE provisioning/status contract and network behavior expectations |
| docs/BACKEND_SPEC.md | Backend endpoint, auth, provider, and error contract specification |

- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — Phase 1 build plan
- [ROADMAP.md](ROADMAP.md) — Full project roadmap
- [docs/planning/IMPLEMENTATION_PLAN_NEXT.md](docs/planning/IMPLEMENTATION_PLAN_NEXT.md) — Detailed implementation sequencing for Phases 2–4
- [docs/planning/TASK_TRACKER.md](docs/planning/TASK_TRACKER.md) — Canonical backlog + per-iteration log for all contributors/agents
- [docs/planning/HANDOFF_NEXT_AGENT.md](docs/planning/HANDOFF_NEXT_AGENT.md) — Practical takeover brief and next-slice implementation notes
- [docs/reference-ui/README.md](docs/reference-ui/README.md) — Canonical location and naming conventions for imported HTML UI reference files
- [companion/README.md](companion/README.md) — Companion PWA workflow for BLE Wi-Fi provisioning

## License

Private. All rights reserved.
