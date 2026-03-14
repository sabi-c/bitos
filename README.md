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

## Docs

- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — Phase 1 build plan
- [../ROADMAP.md](../ROADMAP.md) — Full project roadmap

## License

Private. All rights reserved.
