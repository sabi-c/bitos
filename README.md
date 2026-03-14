# BITOS

A pocket AI companion device. Pi Zero 2W + Whisplay HAT + PiSugar 3.

Hold the button, ask Claude something, hear it answer.

## Quick Start

```bash
# 1. Clone and setup
git clone git@github.com:sabi-c/bitos.git
cd bitos
cp .env.template .env
# Edit .env with your ANTHROPIC_API_KEY

# 2. Install deps
pip install -r requirements.txt

# 3. Run
make dev-server   # Terminal 1: FastAPI backend on :8000
make dev-device   # Terminal 2: Pygame device simulator
make dev-preview  # Terminal 3: Mobile web preview on :5001
```

## Architecture

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

## Docs

- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — Phase 1 build plan
- [ROADMAP.md](ROADMAP.md) — Full project roadmap
- [docs/planning/IMPLEMENTATION_PLAN_NEXT.md](docs/planning/IMPLEMENTATION_PLAN_NEXT.md) — Detailed implementation sequencing for Phases 2–4
- [docs/planning/TASK_TRACKER.md](docs/planning/TASK_TRACKER.md) — Canonical backlog + per-iteration log for all contributors/agents
- [docs/reference-ui/README.md](docs/reference-ui/README.md) — Canonical location and naming conventions for imported HTML UI reference files

## License

Private. All rights reserved.
