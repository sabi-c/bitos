# BITOS — Claude Code Instructions

## What this is
Pocket AI companion device. Pi Zero 2W + 240x280 OLED + single button + speaker.
Mac mini runs the server (FastAPI + Claude API). Device renders UI and captures input.

## Architecture
```
Device (Pi Zero 2W)          Server (Mac mini)
├── Pygame UI (240x280)      ├── FastAPI on :8000
├── Single button input      ├── Claude API (Sonnet primary, Haiku sub-agents)
├── TTS playback             ├── 14 agent tools
├── BLE GATT server          ├── SQLite stores (memory, heartbeat, messages)
├── WiFi/HTTP client         ├── Notification dispatcher
└── Audio pipeline           └── Proactive heartbeat
```

## Critical rules

### Imports
Files under `device/` must NOT use `device.` prefix:
```python
# CORRECT
from audio.tts import TextToSpeech
from screens.base import BaseScreen
from storage.repository import DeviceRepository

# WRONG — causes boot crash
from device.audio.tts import TextToSpeech
```
This is because `device/__init__.py` adds itself to `sys.path`.

### Button mapping
- SHORT_PRESS = next item
- DOUBLE_PRESS = select
- LONG_PRESS = go back
- TRIPLE_PRESS = agent overlay / up
- POWER_GESTURE (5× press) = quick menu

### Display layout (CompositeScreen)
- Status bar: 20px top, full 240px width
- Sidebar: 84px left column
- Right panel: 156px content area
- Action bar: 20px bottom

### Testing
```bash
python3 -m pytest tests/ -x -q  # full suite
```
Pre-existing failures to ignore: `test_render_draws_sidebar`, `test_double_on_thread_moves_to_list`

SDL dummy driver required: `SDL_VIDEODRIVER=dummy` (set in test files)

### Production launch
```bash
# On Pi:
python -m device.main  # with PYTHONPATH=/home/pi/bitos
# Via systemd:
sudo systemctl start bitos-device
```

## Key directories
- `device/` — Pi UI code (94 Python files)
- `server/` — FastAPI backend (28 Python files)
- `tests/` — 103 test files
- `companion/` — PWA companion app (BLE + settings)
- `docs/plans/` — Sprint design + implementation plans
- `scripts/` — Setup and deployment (21 shell scripts)

## Settings sync flow
Companion app → PUT /settings/device → server queues in pending → device polls GET /settings/device/pending every 5s → applies locally via DeviceRepository

## Agent modes
Producer / Hacker / Clown / Monk / Storyteller / Director
Set via settings. Changes system prompt personality.

## TTS fallback chain
Cartesia → Edge TTS (free) → Speechify → Chatterbox → Piper → OpenAI → eSpeak → silent
