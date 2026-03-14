# Coding Session 001 — Initial Repo Scaffold
**Date:** 2026-03-13
**Time:** 17:50–18:42 PST
**Agent:** Antigravity (Claude)
**Conversation ID:** bc3143f2-846a-4f7e-b92d-233b389ab739

---

## Session Objective

Bootstrap the `sabi-c/bitos` GitHub repo from scratch based on two existing spec documents, creating the full Phase 1 project scaffold with implementation plan and testing strategy.

---

## Starting State

- **Workspace:** `/Users/seb/Downloads/Manual Library/Seb's Mind/Bitos Companion device/`
- **Existing spec documents:**
  - `BITOS_SPEC.md` — Hardware spec, display design system, UI screens, voice architecture, build phases
  - `BITOS_BACKEND_SPEC.md` — Repo structure, FastAPI backend, permissions model, Claude integration, phased build plan
- **Existing reference code:**
  - `whisplay-ai-chatbot/python/` — Whisplay HAT drivers (ST7789 display, WM8960 audio, pyaudio, Whisper API)
  - Files studied: `whisplay.py`, `utils.py`, `wakeword.py`, `chatbot-ui.py`
- **Existing prototypes:**
  - `bitos-screen-proto.html` — HTML mockup of the UI layout
  - `index.html` — Interactive web prototype with multiple screens
- **No git repo existed yet** — everything was loose files in the workspace folder

---

## What Was Done

### 1. Research & Planning

| Step | Detail |
|---|---|
| Read `BITOS_SPEC.md` | Full hardware spec (Pi Zero 2W, Whisplay HAT, PiSugar 3), 240×280 pixel display design system (colors, fonts, borders, layout), all UI screens (lock, sidebar, chat, focus, mail, tasks, settings), voice architecture (wake word → STT → Claude → TTS), and 4-phase build order |
| Read `BITOS_BACKEND_SPEC.md` | Repo structure (`device/` + `server/`), FastAPI backend with `/health` and `/chat` streaming endpoints, permissions model (5 scopes), Claude integration with streaming, env config, Makefile targets, and phased milestones |
| Read whisplay reference code | `whisplay.py` (ST7789 SPI driver, RGB565 conversion), `utils.py` (text wrapping, image conversion), `wakeword.py` (keyword detection), `chatbot-ui.py` (audio pipeline, Whisper API, UI rendering) |
| Surveyed workspace | Found HTML prototypes, noted what could be reused vs built fresh |

### 2. Created `ROADMAP.md`

**Location:** `/Bitos Companion device/ROADMAP.md` (workspace root, not in bitos/)

7-phase roadmap from initial bootstrap through companion app:
1. **Voice Works** — Repo scaffold, Pygame simulator, streaming chat
2. **Navigation + Persistence** — Lock screen, sidebar, SQLite, history
3. **Tasks + MCP** — Things 3 integration, task panel, quick capture
4. **All Screens** — Focus timer, mail, settings, notifications
5. **Hardware Deploy** — ST7789 driver, WM8960 audio, systemd
6. **Global Workspace** — Knowledge graph, morning brief, proactive AI
7. **Companion App** — iOS/Mac WiFi config, keyboard relay

### 3. Created Full Repo Scaffold

**Location:** `/Bitos Companion device/bitos/`
**GitHub:** `sabi-c/bitos` (private)
**Files:** 34 files, 1,653 lines

#### Directory structure created:
```
bitos/
├── README.md
├── IMPLEMENTATION_PLAN.md
├── .env.template
├── .gitignore
├── requirements.txt
├── Makefile
├── render.yaml
├── device/
│   ├── main.py
│   ├── __init__.py
│   ├── assets/fonts/PressStart2P.ttf
│   ├── display/
│   │   ├── __init__.py
│   │   ├── tokens.py          ← design constants
│   │   ├── driver.py          ← PygameDriver + ST7789 stub
│   │   └── animator.py        ← step-based animation engine
│   ├── input/
│   │   ├── __init__.py
│   │   └── handler.py         ← button gesture detection
│   ├── audio/
│   │   ├── __init__.py
│   │   └── pipeline.py        ← stub (desktop mode)
│   ├── screens/
│   │   ├── __init__.py
│   │   ├── base.py            ← BaseScreen ABC
│   │   ├── manager.py         ← screen stack + transitions
│   │   ├── boot.py            ← boot animation (4 orbs)
│   │   ├── panels/
│   │   │   ├── __init__.py
│   │   │   └── chat.py        ← chat panel with streaming
│   │   └── subscreens/
│   │       └── __init__.py
│   ├── overlays/
│   │   └── __init__.py
│   └── client/
│       ├── __init__.py
│       └── api.py             ← HTTP client to backend
├── server/
│   ├── __init__.py
│   ├── main.py                ← FastAPI + Claude streaming
│   └── config.py              ← env loading
└── web_preview/
    ├── server.py              ← MJPEG preview server
    ├── requirements.txt
    └── templates/
        └── index.html         ← mobile preview page
```

### 4. Key Technical Decisions Made

| Decision | Rationale |
|---|---|
| **Pygame for desktop dev** | Fast iteration without hardware. 240×280 internal surface scaled 2× to 480×560 window. Pixel-perfect with `NEAREST` scaling |
| **MJPEG web preview** | Captures Pygame frames as JPEG → streams via Flask multipart — works on any phone browser, no app needed |
| **SSE streaming for chat** | Server streams Claude response as `text/event-stream`, client yields chunks — matches the "text appearing line by line" spec requirement |
| **Step-based animations only** | Per spec: "ALL animations must use steps()". `StepAnimator` class provides discrete-frame advancement, no smooth interpolation |
| **Button gesture accumulation** | Multi-tap detection uses a time window (600ms for triple) before finalizing, avoids false positives |
| **render.yaml included** | Two Render.com web services (server + preview) for remote testing on any device |
| **Press Start 2P font** | Downloaded from Google Fonts. 118KB TTF. Pixel-perfect at 6/8/10px sizes per spec |
| **Audio pipeline stubbed** | Returns `is_available()=False` on desktop. Real impl deferred to Phase 5 when hardware is ready |

### 5. GitHub Push

- **Repo:** `sabi-c/bitos` (private)
- **URL:** https://github.com/sabi-c/bitos
- **Branch:** `main`
- **Commit:** `ca680a3` — "feat: initial bitos repo scaffold"
- **Git config:** `user.name=sabi-c`, `user.email=sabi-c@users.noreply.github.com`

---

## What Still Needs to Be Done

### Phase 1 Completion (next session)
- [ ] Install dependencies and verify `make dev-server` runs
- [ ] Add `ANTHROPIC_API_KEY` to `.env` and test `/chat` endpoint
- [ ] Run `make dev-device` and verify boot screen animation
- [ ] Test full chat flow: type message → streaming response renders
- [ ] Test web preview (`make dev-preview`) on mobile
- [ ] Deploy to Render.com and verify remote access
- [ ] Fix any import path issues (may need `sys.path` adjustments)

### Phase 2 (after Phase 1 works)
- [ ] Lock screen with clock
- [ ] Sidebar navigation panel
- [ ] SQLite database for chat history
- [ ] Session persistence across restarts

### Phases 3–7
See `ROADMAP.md` for full breakdown.

---

## Files for Other Agents to Read First

1. **`IMPLEMENTATION_PLAN.md`** — Architecture, every file explained, testing strategy, QA checklist
2. **`ROADMAP.md`** (workspace root) — Full project phasing
3. **`BITOS_SPEC.md`** (workspace root) — Hardware + UI design spec
4. **`BITOS_BACKEND_SPEC.md`** (workspace root) — Backend + repo structure spec
5. **This session doc** — What was done and what's left

---

## Environment Notes

- **OS:** macOS
- **Python:** 3.x (needs `pip install -r requirements.txt`)
- **Key deps:** `pygame`, `fastapi`, `uvicorn`, `anthropic`, `httpx`, `flask`, `Pillow`
- **GitHub auth:** `gh` CLI logged in as `sabi-c` via keyring
- **No virtual env was created** — deps should be installed before first run
