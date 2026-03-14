# BITOS · IMPLEMENTATION PLAN
## Phase 1 — "Voice Works" · Repo Bootstrap

---

## Goal

Bootstrap the `bitos/` repo so you can **hold the button, ask Claude something, and see the streaming response on screen**. Desktop-first (Pygame simulator), with a web preview mode for mobile testing on Render.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  Device (Pygame on desktop / ST7789 on Pi)          │
│  ┌──────────────────────────────────────────────┐   │
│  │  main.py  ─  event loop @ 30 FPS             │   │
│  │    ├─ display/driver.py   (Pygame / ST7789)   │   │
│  │    ├─ input/handler.py    (button gestures)   │   │
│  │    ├─ screens/manager.py  (screen stack)      │   │
│  │    │    ├─ boot.py        (startup anim)      │   │
│  │    │    └─ panels/chat.py (chat view)         │   │
│  │    ├─ audio/pipeline.py   (mic → STT → TTS)  │   │
│  │    └─ client/api.py       (HTTP to server)    │   │
│  └──────────────────────────────────────────────┘   │
│                        │ HTTP (SSE stream)           │
│  ┌─────────────────────▼────────────────────────┐   │
│  │  Server (FastAPI)                             │   │
│  │    ├─ GET  /health                            │   │
│  │    └─ POST /chat  → stream Claude response    │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## Repo Structure

```
bitos/
├── README.md
├── IMPLEMENTATION_PLAN.md        ← this file
├── .env.template
├── .gitignore
├── requirements.txt
├── Makefile
│
├── device/
│   ├── main.py                   ← device entry point (Pygame loop)
│   ├── __init__.py
│   ├── assets/
│   │   └── fonts/
│   │       └── PressStart2P.ttf
│   ├── display/
│   │   ├── __init__.py
│   │   ├── driver.py             ← PygameDriver / ST7789Driver(stub)
│   │   ├── tokens.py             ← all design constants
│   │   └── animator.py           ← stepped animation engine
│   ├── input/
│   │   ├── __init__.py
│   │   └── handler.py            ← button gesture detection
│   ├── audio/
│   │   ├── __init__.py
│   │   └── pipeline.py           ← mic/STT/TTS (stub on desktop)
│   ├── screens/
│   │   ├── __init__.py
│   │   ├── base.py               ← BaseScreen ABC
│   │   ├── manager.py            ← screen stack + transitions
│   │   ├── boot.py               ← boot animation screen
│   │   ├── panels/
│   │   │   ├── __init__.py
│   │   │   └── chat.py           ← chat input/output panel
│   │   └── subscreens/
│   │       └── __init__.py
│   ├── overlays/
│   │   └── __init__.py
│   └── client/
│       ├── __init__.py
│       └── api.py                ← HTTP client to backend
│
├── server/
│   ├── __init__.py
│   ├── main.py                   ← FastAPI app
│   └── config.py                 ← env loading
│
└── web_preview/
    ├── server.py                 ← Flask app that serves Pygame frames as MJPEG
    ├── templates/
    │   └── index.html            ← mobile-friendly page with live preview
    └── requirements.txt
```

---

## Design Tokens (from BITOS_SPEC.md)

| Token | Value | Notes |
|---|---|---|
| `PHYSICAL_W` | 240px | ST7789 native |
| `PHYSICAL_H` | 280px | ST7789 native |
| `SCALE` | 2 | Desktop sim only |
| `BLACK` | `(0, 0, 0)` | Background |
| `WHITE` | `(255, 255, 255)` | Primary text |
| `DIM1` | `(204, 204, 204)` | 80% white |
| `DIM2` | `(153, 153, 153)` | 60% |
| `DIM3` | `(102, 102, 102)` | 40% |
| `DIM4` | `(51, 51, 51)` | 20% |
| `HAIRLINE` | `(26, 26, 26)` | Borders |
| Font | Press Start 2P | Google Fonts, pixel-perfect |
| `FONT_TITLE` | 10px | |
| `FONT_BODY` | 8px | Primary text size |
| `FONT_SMALL` | 6px | Status text |

---

## File-by-File Breakdown

### 1. `device/display/tokens.py`
All design constants. Single source of truth for colors, sizes, padding.

### 2. `device/display/driver.py`
- **`DisplayDriver`** (ABC): `init()`, `update(surface)`, `quit()`, `get_surface()`
- **`PygameDriver`**: Opens 480×560 window (2× scaled). Renders from 240×280 internal surface. Handles `pygame.QUIT`.
- **`ST7789Driver`**: **Stub only** — will port from whisplay.py `_init_display()`, `draw_image()`, `set_window()` in Phase 5.
- Env var `BITOS_DISPLAY=pygame|st7789` selects driver.

### 3. `device/display/animator.py`
- **`StepAnimator`**: Discrete-step animation engine.
- All animations use `steps()` — no smooth interpolation (per spec).
- Provides presets: `blink_cursor`, `typing_dots`, `loading_bar`, `orb_rotate`.

### 4. `device/input/handler.py`
- **`ButtonHandler`**: Processes raw press/release → gesture events.
- Gestures: `SHORT_PRESS` (<600ms), `LONG_PRESS` (≥600ms hold), `DOUBLE_PRESS` (2× within 400ms), `TRIPLE_PRESS` (3× within 600ms).
- Desktop: Space bar = button. Arrow keys = scroll (for later).
- Callback system: `on(event_type, callback)`.

### 5. `device/screens/base.py`
- **`BaseScreen`** (ABC): `render(surface)`, `handle_input(event)`, `on_enter()`, `on_exit()`, `update(dt)`.

### 6. `device/screens/manager.py`
- **`ScreenManager`**: Push/pop screen stack. White-flash transition (1 frame of white). Delegates `render()` and `handle_input()` to top screen.

### 7. `device/screens/boot.py`
- 4 pixel orbs (4×4px white squares) rotating in 8 steps.
- "BITOS" text centered, blinking cursor.
- Auto-advances after 3s or any button press → transitions to chat panel.

### 8. `device/screens/panels/chat.py`
- **Phase 1 simplified**: Text input via keyboard (type + Enter to send).
- Streaming response rendered line-by-line as chunks arrive from backend.
- Uses `BackendClient.chat()` for async streaming.

### 9. `device/client/api.py`
- **`BackendClient`**:
  - `health() → bool` — GET `/health`, 3s timeout.
  - `chat(message) → Generator[str]` — POST `/chat`, yields streamed text chunks.
  - Base URL from `BITOS_SERVER_URL` env var (default `http://localhost:8000`).

### 10. `device/audio/pipeline.py`
- **`AudioPipeline`** (stub):
  - `is_available() → bool` — returns False on macOS.
  - `record()`, `transcribe()`, `speak()` — raise NotImplementedError.
  - Will port from whisplay-ai-chatbot in Phase 5.

### 11. `device/main.py`
- Entry point. Initializes driver → handler → screen manager → pushes boot screen.
- Main loop: `handle_events() → update(dt) → render()` at 30 FPS cap.
- Starts backend client in background thread.

### 12. `server/main.py`
- FastAPI with:
  - `GET /health` → `{"status": "ok", "model": "claude-sonnet-4-6"}`
  - `POST /chat` → accepts `{"message": "..."}`, streams Claude response via SSE.
- Uses `anthropic.Anthropic().messages.stream()`.

### 13. `server/config.py`
- Loads `.env` via python-dotenv.
- Exports: `ANTHROPIC_API_KEY`, `SERVER_HOST`, `SERVER_PORT`, `MODEL_NAME`.

---

## What We're Porting from whisplay-ai-chatbot

| Source file | Take | Skip |
|---|---|---|
| `whisplay.py` | ST7789 init sequence, SPI commands, `set_window()`, `draw_image()`, RGB565 conversion | Radxa code, RGB LED PWM, platform detection (simplified for Pi only) |
| `utils.py` | `image_to_rgb565()` concepts, `wrap_text()` logic | Emoji SVG rendering, cairosvg dependency |
| `chatbot-ui.py` | Audio record/playback loop, pyaudio config, Whisper API call | UI rendering (replaced by Pygame) |
| `wakeword.py` | Full file, mostly unchanged | — (optional feature, Phase 5+) |

---

## Testing & Preview Strategy

### Local Desktop Testing

```bash
# Terminal 1 — Start backend
cd bitos && make dev-server

# Terminal 2 — Start Pygame device
cd bitos && make dev-device
```

### Web Preview (for Mobile Testing)

The `web_preview/` module provides a **live MJPEG stream of the Pygame framebuffer** over HTTP, so you can view the device UI in any mobile browser.

#### How it works:
1. The Pygame device loop captures each frame as a JPEG
2. A Flask server streams these frames as `multipart/x-mixed-replace` (MJPEG)
3. A responsive HTML page wraps the stream in a phone-shaped viewport (240×280)
4. Touch events on the page are translated back to button press/release events

#### Run locally:
```bash
make dev-preview
# Opens http://localhost:5001 — view on phone via same WiFi
```

#### Deploy to Render.com:
```bash
# render.yaml is included — one-click deploy
# The web preview runs as a Web Service
# The FastAPI backend runs as a second Web Service
# Both auto-deploy on push to main
```

#### `render.yaml` included:
```yaml
services:
  - type: web
    name: bitos-server
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn server.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false

  - type: web
    name: bitos-preview
    runtime: python
    buildCommand: pip install -r web_preview/requirements.txt -r requirements.txt
    startCommand: python web_preview/server.py
    envVars:
      - key: BITOS_SERVER_URL
        fromService:
          name: bitos-server
          type: web
          property: host
```

### Test Matrix

| Test | Command | Expected |
|---|---|---|
| Server health | `curl localhost:8000/health` | `{"status":"ok"}` |
| Server chat | `curl -X POST localhost:8000/chat -d '{"message":"hi"}'` | Streaming text |
| Pygame window | `make dev-device` | 480×560 window, boot anim plays |
| Boot → chat transition | Wait 3s or press space | White flash → chat screen |
| Button gestures | Space bar tap / hold / double-tap | Console logs gesture type |
| Chat send | Type message + Enter | Streaming response renders |
| Web preview | `make dev-preview` → open on phone | Live 240×280 device view |
| Render deploy | `git push` to main | Both services auto-deploy |

### Manual QA Checklist

- [ ] Boot screen shows 4 orbs + "BITOS" text
- [ ] Orbs animate in discrete steps (not smooth)
- [ ] Boot auto-advances after 3s
- [ ] Space bar tap logs SHORT_PRESS
- [ ] Space bar hold (>600ms) logs LONG_PRESS
- [ ] Double space tap logs DOUBLE_PRESS
- [ ] Chat screen accepts keyboard input
- [ ] Typing + Enter sends message to backend
- [ ] Response streams in line-by-line (not all at once)
- [ ] Text wraps correctly at 240px width
- [ ] Font is Press Start 2P, pixel-perfect (no anti-aliasing)
- [ ] Web preview shows live device view on phone
- [ ] Web preview touch triggers button events

---

## Phase 1 Completion Criteria

✅ `make dev-server` starts FastAPI on :8000
✅ `make dev-device` opens Pygame window with boot screen
✅ Boot screen plays orb animation → transitions to chat
✅ Type a message → see streaming Claude response on screen
✅ `make dev-preview` → view and interact on phone browser
✅ All code pushed to private GitHub repo `sabi-c/bitos`

---

## Build Order

1. Repo scaffold (all dirs, `__init__.py` files, top-level configs)
2. `tokens.py` — design constants
3. `driver.py` — Pygame display driver
4. `animator.py` — step animation engine
5. `handler.py` — button gesture detection
6. `base.py` + `manager.py` — screen system
7. `boot.py` — boot screen
8. `server/config.py` + `server/main.py` — FastAPI backend
9. `client/api.py` — HTTP client
10. `chat.py` — chat panel
11. `main.py` — device entry point (wire everything)
12. `web_preview/` — MJPEG preview server
13. `Makefile` targets
14. Test everything, push to GitHub

---

## Next Phases (Preview)

| Phase | Focus | Key additions |
|---|---|---|
| **2** | Navigation + persistence | Lock screen, sidebar nav, SQLite, history |
| **3** | Tasks + MCP | Things integration, task panel, quick capture |
| **4** | All screens | Focus, mail, settings, notifications |
| **5** | Hardware deploy | ST7789 driver, WM8960 audio, systemd |
| **6** | Global workspace | Shared memory, morning brief, proactive AI |
| **7** | Companion app | iOS/Mac WiFi config, keyboard relay |
