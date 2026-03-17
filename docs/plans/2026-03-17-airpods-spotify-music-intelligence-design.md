# AirPods + Spotify + Music Intelligence for BITOS

**Date:** 2026-03-17
**Status:** Design
**Hardware:** Pi Zero 2W (BCM43436s BT 4.2) + WM8960 (WhisPlay HAT) + Mac mini server

---

## Table of Contents

1. [AirPod Audio Routing Architecture](#1-airpod-audio-routing-architecture)
2. [Gesture Mapping Implementation](#2-gesture-mapping-implementation)
3. [Spotify Integration](#3-spotify-integration)
4. [Agent Music Tools](#4-agent-music-tools)
5. [Music Logging & Taste Profile](#5-music-logging--taste-profile)
6. [AirPod Mode UX](#6-airpod-mode-ux)
7. [Implementation Plan](#7-implementation-plan)

---

## 1. AirPod Audio Routing Architecture

### 1.1 Current State

The existing codebase already supports Bluetooth audio:

- **`device/bluetooth/audio_manager.py`** — Full `BluetoothAudioManager` with scan, pair, connect, disconnect, forget. Already handles PulseAudio sink switching (`pactl set-default-sink`) and ALSA fallback (bluealsa `.asoundrc` writing).
- **`device/audio/player.py`** — `AudioPlayer` already detects BT audio via `_is_bt_audio_active()` and routes playback through `paplay` (PulseAudio) when a Bluetooth sink is active, falling back to `aplay` (ALSA).
- **`device/screens/panels/bt_audio.py`** — Complete BT audio settings panel with scanning, pairing, connecting UI.
- **`device/audio/pipeline.py`** — `WM8960Pipeline` handles recording (arecord) and playback (aplay/paplay).

**What already works:** Pair AirPods, connect, route TTS audio output through them via PulseAudio.

### 1.2 What's Missing for Full AirPod Integration

#### A2DP Source (Pi -> AirPods audio output)

**Status: Already functional.** When AirPods connect, PulseAudio automatically creates a Bluetooth A2DP sink. The existing `_switch_audio_to_bt()` in `audio_manager.py` sets this as the default sink. All `paplay` calls in `player.py` will route through it.

#### HFP (Hands-Free Profile) for AirPod Mic Input

**This is the critical gap.** The current recording pipeline uses the WM8960 mic exclusively (`arecord -D default`). When AirPods are connected, we need to also capture audio from the AirPod mic for voice commands.

**Pi Zero 2W HFP support:**
- BCM43436s supports Bluetooth 4.2 (Classic BT + BLE). HFP 1.7 is supported.
- PulseAudio + `pulseaudio-module-bluetooth` (or PipeWire) can expose the HFP mic as a PulseAudio source.
- Pi OS Bookworm ships PipeWire by default, which handles HFP natively through `wireplumber`.
- The AirPod mic appears as a separate PulseAudio/PipeWire source when HFP is active.

**Catch:** A2DP and HFP cannot run simultaneously on the same device in classic Bluetooth. When HFP activates (for mic), audio quality drops to 8kHz/16kHz mono (telephony codec). This is standard Bluetooth behavior, not a Pi limitation.

**Solution: Hybrid routing.**

```
IDLE / MUSIC PLAYBACK:
  Output: A2DP sink (AirPods) — high quality stereo
  Input:  WM8960 mic (device) — always available

VOICE CONVERSATION:
  Option A (recommended): Keep A2DP for output, use WM8960 mic for input
  Option B: Switch to HFP (mic + speaker on AirPods, but 8kHz quality)
```

**Recommendation: Option A.** Use the device's WM8960 mic for recording even when AirPods are connected. The user speaks toward the device (which they're holding/wearing), and hears the agent's response through AirPods. This avoids the A2DP->HFP quality drop entirely.

For "AirPod-only" scenarios (device in pocket, AirPods-only interaction), offer HFP as a toggleable setting.

#### BLE + Classic BT Coexistence

**BCM43436s supports both BLE and Classic BT simultaneously.** The GATT server (companion app BLE) and A2DP/HFP (AirPods) use different protocol stacks and do not conflict. The existing `BitosGATTServer` runs on BLE while AirPods connect via Classic BT.

**Tested coexistence matrix:**
| Connection | Protocol | Coexists? |
|---|---|---|
| Companion app (BLE GATT) | BLE | Yes |
| AirPods A2DP (audio out) | Classic BT | Yes |
| AirPods HFP (mic in) | Classic BT | Yes, but downgrades A2DP |
| WiFi | 2.4GHz shared radio | Yes, some throughput reduction |

#### PulseAudio vs PipeWire

Pi OS Bookworm ships PipeWire. Both work for BT audio routing. The existing code uses `pactl` which is compatible with both (PipeWire provides a PulseAudio compatibility layer).

**Recommendation: Stick with whatever Pi OS ships.** The `pactl` commands in `audio_manager.py` work identically on both. No code changes needed.

#### Latency

- **A2DP output latency:** 100-200ms (codec-dependent). SBC codec is default, AAC is better but may not be supported by PipeWire on Pi. Acceptable for TTS playback and music.
- **HFP mic latency:** 30-80ms. Good enough for voice commands.
- **WM8960 mic latency:** <10ms (local hardware). Best option for recording.

### 1.3 Audio Routing Implementation

New module: **`device/bluetooth/audio_router.py`**

```python
class AudioRouter:
    """Manages audio input/output routing based on connected devices.

    Routes:
      - Output: AirPods (BT A2DP) when connected, else WM8960 speaker
      - Input: WM8960 mic (default), or AirPods HFP mic (if airpod_mic_mode=on)
    """

    def __init__(self, bt_audio_manager, repository):
        self._bt = bt_audio_manager
        self._repo = repository
        self._airpod_mode = False

    @property
    def output_device(self) -> str:
        """Current audio output: 'airpods' or 'speaker'."""
        if self._bt.is_audio_routed_to_bt():
            return "airpods"
        return "speaker"

    @property
    def input_device(self) -> str:
        """Current audio input: 'wm8960' or 'airpods_hfp'."""
        if self._airpod_mode and self._use_airpod_mic():
            return "airpods_hfp"
        return "wm8960"

    def enter_airpod_mode(self):
        """Called when AirPods connect. Switches UI and audio routing."""
        self._airpod_mode = True

    def exit_airpod_mode(self):
        """Called when AirPods disconnect. Restores speaker routing."""
        self._airpod_mode = False

    def duck_audio(self, target_volume: float = 0.15):
        """Lower music volume for agent speech (music ducking)."""
        # pactl set-sink-volume <sink> <volume>

    def restore_audio(self):
        """Restore music volume after agent speech."""
```

### 1.4 Connection Detection & Auto-Switch

Add to `BluetoothAudioManager`:

```python
def detect_device_type(self, address: str) -> str:
    """Detect if connected device is AirPods (vs generic headphones)."""
    info = self._get_device_info(address)
    if info:
        name = info.get("Name", "").lower()
        if "airpods" in name:
            return "airpods"
    return "headphones"
```

Wire into `connect()` to auto-detect AirPods and trigger `enter_airpod_mode()` on the `AudioRouter`.

---

## 2. Gesture Mapping Implementation

### 2.1 What AirPods Send (from existing research)

Per `docs/plans/2026-03-17-airpod-gesture-controls-research.md`:

| Gesture | AVRCP Command | Detectable on Pi? |
|---|---|---|
| Single tap/squeeze | Play/Pause | YES |
| Double tap/squeeze | Next Track | YES |
| Triple tap/squeeze | Previous Track | YES |
| Long press/squeeze | Siri/ANC toggle | NO (handled internally) |
| Stem slide (Pro) | Volume Up/Down | YES |

### 2.2 Detection Method: D-Bus MediaPlayer1

Primary approach (already researched in the AVRCP doc). New module:

**`device/bluetooth/avrcp_listener.py`**

```python
"""AVRCP media key listener using D-Bus MediaPlayer1 interface.

Monitors BlueZ D-Bus for AVRCP events from connected BT audio devices
(AirPods, headphones) and emits BITOS input events.
"""
import asyncio
import logging
import threading
import time

logger = logging.getLogger(__name__)

# Debounce window — AirPods send rapid Play/Pause for single tap
_DEBOUNCE_MS = 150

# AVRCP events emitted
AVRCP_PLAY_PAUSE = "AVRCP_PLAY_PAUSE"
AVRCP_NEXT = "AVRCP_NEXT"
AVRCP_PREVIOUS = "AVRCP_PREVIOUS"
AVRCP_VOLUME_UP = "AVRCP_VOLUME_UP"
AVRCP_VOLUME_DOWN = "AVRCP_VOLUME_DOWN"


class AVRCPListener:
    def __init__(self, on_event=None):
        self._on_event = on_event
        self._running = False
        self._thread = None
        self._last_event_time = 0
        self._last_event_name = ""

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="avrcp-listener", daemon=True
        )
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._monitor())
        except Exception as exc:
            logger.error("avrcp_listener_failed: %s", exc)
            self._try_evdev_fallback()
        finally:
            loop.close()

    async def _monitor(self):
        """Monitor D-Bus for MediaPlayer1 property changes."""
        try:
            from dbus_next.aio import MessageBus
            from dbus_next import BusType
        except ImportError:
            logger.warning("dbus-next not installed, trying evdev fallback")
            self._try_evdev_fallback()
            return

        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

        def on_message(msg):
            if msg.member != "PropertiesChanged":
                return
            args = msg.body
            if len(args) < 2:
                return
            iface, changed = args[0], args[1]
            if iface != "org.bluez.MediaPlayer1":
                return
            if "Status" in changed:
                status = changed["Status"].value
                self._handle_status(status)

        bus.add_message_handler(on_message)

        # Subscribe to MediaPlayer1 property changes
        reply = await bus.call(
            bus.new_method_call(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "AddMatch",
            ).body_from_args(
                "type='signal',sender='org.bluez',"
                "interface='org.freedesktop.DBus.Properties',"
                "arg0='org.bluez.MediaPlayer1'"
            )
        )

        while self._running:
            await asyncio.sleep(0.1)

    def _handle_status(self, status: str):
        """Debounce and emit AVRCP event."""
        now = time.monotonic() * 1000
        if now - self._last_event_time < _DEBOUNCE_MS:
            return
        self._last_event_time = now

        if status in ("playing", "paused"):
            self._emit(AVRCP_PLAY_PAUSE)

    def _emit(self, event: str):
        logger.debug("avrcp_event: %s", event)
        if self._on_event:
            self._on_event(event)

    def _try_evdev_fallback(self):
        """Fall back to evdev input device monitoring."""
        try:
            import evdev
        except ImportError:
            logger.warning("evdev not installed, AVRCP listener disabled")
            return
        # ... evdev fallback as documented in research
```

### 2.3 Context-Dependent Gesture Mapping

Instead of mapping AVRCP events directly to button actions, create a parallel input source. Each screen decides what AirPod gestures mean in context.

**Mapping table by context:**

| Context | Play/Pause | Next | Previous | Vol+/- |
|---|---|---|---|---|
| **Home screen** | Start voice input | Next widget | Previous widget | Volume |
| **Chat screen** | Toggle recording | Next message | Previous message | Volume |
| **Music playing** | Play/pause music | Next track | Previous track | Volume |
| **Agent speaking (TTS)** | Stop/skip TTS | - | - | Volume |
| **Recording voice** | Stop recording + send | Cancel recording | - | Volume |

Wire into `device/main.py` event loop:

```python
from bluetooth.avrcp_listener import AVRCPListener

# In initialization:
avrcp = AVRCPListener(on_event=lambda e: _handle_avrcp(e))
avrcp.start()

def _handle_avrcp(event: str):
    """Route AVRCP event to active screen with source tag."""
    screen_manager.handle_action(event, source="airpod")
```

### 2.4 What's NOT Detectable

- **Long press** — handled inside AirPods firmware (Siri/ANC). Cannot be captured.
- **Ear detection (in/out)** — AirPods report this to iPhone but not to generic BT hosts. The Pi cannot detect ear insertion/removal.
- **ANC/Transparency mode** — controlled by AirPods firmware. Pi cannot read or set it.
- **Battery level** — AirPods send battery info via Apple-proprietary HFP AT commands. Partially parseable (see section 6.3) but unreliable on Linux.

---

## 3. Spotify Integration

### 3.1 Architecture Decision: Spotify Connect vs API vs Hybrid

Three approaches, evaluated:

#### Option A: Spotify Connect (librespot/spotifyd on Pi)

- Pi appears as a Spotify Connect device. User selects "BITOS" in Spotify app.
- Audio streams directly to Pi, then routes to AirPods via BT A2DP.
- **Pro:** Real audio playback, offline-capable (Premium), full quality control.
- **Con:** Pi Zero 2W CPU may struggle with audio decoding + BT A2DP encoding simultaneously. `librespot` uses ~30% CPU on Pi Zero 2W. Combined with BT stack, display, and agent — too tight.
- **Con:** Requires Spotify Premium.
- **Audio path:** Spotify cloud -> Pi (librespot decode) -> PulseAudio -> BT A2DP -> AirPods

#### Option B: API-Only (music plays on phone, Pi controls via API)

- Spotify plays on user's phone (or another device). Pi sends Spotify Web API commands.
- AirPods connected to phone for audio. Pi uses its own speaker for TTS.
- **Pro:** Zero CPU load on Pi for music. Phone handles all audio.
- **Con:** AirPods can only connect to one device at a time (without Automatic Switching, which requires Apple ecosystem). User must manually switch AirPods between phone and Pi.
- **Con:** Agent TTS and music can't mix — they're on different audio paths.
- **Verdict:** Breaks the "AirPods as primary audio" requirement.

#### Option C: Hybrid — Spotify Connect on Mac mini, Audio Forwarded to Pi (RECOMMENDED)

- Mac mini runs `spotifyd` (Spotify Connect receiver). Appears as "BITOS" in Spotify app.
- Mac mini streams decoded audio to Pi via WiFi (low-latency PCM/opus over WebSocket).
- Pi mixes music audio with TTS and sends combined output to AirPods via BT A2DP.
- **Pro:** Mac mini has abundant CPU. Pi only receives pre-decoded audio. Agent can duck music, mix TTS, and control playback — all in one audio path.
- **Pro:** Pi controls Spotify via Web API (play, pause, skip, search, queue).
- **Pro:** Mac mini can also use Spotify Web API for metadata (now playing, recommendations).

**Alternative within Option C:** Skip audio forwarding entirely. Run `spotifyd` ON the Pi, but use a lightweight build. `spotifyd` can be compiled for ARM with minimal dependencies and uses ~15% CPU for audio decode on Pi Zero 2W. With the new Pi Zero 2W (quad-core), this is viable if we keep the decode task pinned to one core.

**Final recommendation: `spotifyd` on Pi Zero 2W** with Spotify Web API on Mac mini server for metadata/control. This keeps the audio path simple (Pi -> AirPods) and gives the agent full control.

### 3.2 Spotify Setup

#### spotifyd on Pi (audio playback)

```bash
# Install spotifyd (Rust binary, pre-built ARM available)
wget https://github.com/Spotifyd/spotifyd/releases/latest/download/spotifyd-linux-armhf-slim.tar.gz
tar xzf spotifyd-linux-armhf-slim.tar.gz
sudo mv spotifyd /usr/local/bin/

# Config: /home/pi/.config/spotifyd/spotifyd.conf
[global]
username = "spotify_username"
password = "spotify_password"   # or use password_cmd for keyring
backend = "pulseaudio"          # routes through PulseAudio -> BT A2DP
device_name = "BITOS"
bitrate = 160                   # 96/160/320 — 160 is good balance for BT
volume_normalisation = true
device_type = "speaker"
```

When AirPods are connected, PulseAudio routes spotifyd's output through the BT A2DP sink automatically (same mechanism that routes TTS).

#### Spotify Web API (metadata + control)

New server module: **`server/integrations/spotify_adapter.py`**

```python
"""Spotify Web API adapter for BITOS.

Handles OAuth2 PKCE flow (headless device), playback control,
search, recommendations, and now-playing metadata.

Env vars:
    SPOTIFY_CLIENT_ID    — from Spotify Developer Dashboard
    SPOTIFY_CLIENT_SECRET — (optional, for auth code flow)
    SPOTIFY_REDIRECT_URI — callback URL for OAuth
    SPOTIFY_REFRESH_TOKEN — persisted after initial auth
"""
```

Uses `spotipy` library (or raw `httpx` calls to avoid dependency).

#### OAuth on Headless Pi

Spotify requires browser-based OAuth. Options:

1. **Device Code Flow** — Not supported by Spotify API (as of 2026).
2. **Auth via companion app** — User taps "Connect Spotify" in BITOS companion PWA. Companion opens Spotify OAuth in browser, receives token, sends to BITOS server via API.
3. **Auth via server web UI** — Mac mini serves an auth page at `http://bitos.local:8000/spotify/auth`. User visits on phone/laptop, completes OAuth, token stored on server.

**Recommendation: Option 3** (server web UI auth). Same pattern as the existing companion app setup flow. Token refresh is handled by `spotipy` automatically.

### 3.3 Spotify Adapter API

```python
class SpotifyAdapter:
    """Spotify Web API wrapper for agent tools."""

    # Playback control
    async def play(self, uri: str = None, context_uri: str = None) -> bool
    async def pause(self) -> bool
    async def next_track(self) -> bool
    async def previous_track(self) -> bool
    async def seek(self, position_ms: int) -> bool
    async def set_volume(self, volume_percent: int) -> bool
    async def shuffle(self, state: bool) -> bool
    async def repeat(self, state: str) -> bool  # off/track/context

    # Now playing
    async def get_now_playing(self) -> dict | None
    #  Returns: {track, artist, album, album_art_url, progress_ms, duration_ms, is_playing}

    # Search & browse
    async def search(self, query: str, types: list[str] = ["track"]) -> list[dict]
    async def get_recommendations(self, seed_tracks: list[str] = None,
                                   seed_artists: list[str] = None,
                                   seed_genres: list[str] = None) -> list[dict]

    # Queue & playlists
    async def add_to_queue(self, uri: str) -> bool
    async def get_queue(self) -> list[dict]
    async def get_playlists(self, limit: int = 20) -> list[dict]
    async def get_playlist_tracks(self, playlist_id: str) -> list[dict]

    # History (for music logging)
    async def get_recently_played(self, limit: int = 50) -> list[dict]

    # User profile
    async def get_user_profile(self) -> dict
    async def get_top_items(self, type: str = "tracks", time_range: str = "medium_term") -> list[dict]
```

### 3.4 Music Ducking (Talk Over Music)

When the agent needs to speak while music is playing:

```python
class MusicDucker:
    """Duck Spotify playback volume during agent TTS output."""

    DUCK_VOLUME = 15      # percent (quiet background)
    NORMAL_VOLUME = 100   # percent (restored after TTS)
    FADE_STEPS = 5        # smooth fade
    FADE_INTERVAL = 0.05  # seconds between steps

    async def duck(self):
        """Lower music volume for agent speech."""
        # Use pactl to lower the BT sink volume
        # This is faster and more reliable than Spotify API volume
        for step in range(self.FADE_STEPS):
            vol = self.NORMAL_VOLUME - (self.NORMAL_VOLUME - self.DUCK_VOLUME) * (step + 1) / self.FADE_STEPS
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{int(vol)}%"],
                          capture_output=True, timeout=2)
            await asyncio.sleep(self.FADE_INTERVAL)

    async def restore(self):
        """Restore music volume after agent speech."""
        for step in range(self.FADE_STEPS):
            vol = self.DUCK_VOLUME + (self.NORMAL_VOLUME - self.DUCK_VOLUME) * (step + 1) / self.FADE_STEPS
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{int(vol)}%"],
                          capture_output=True, timeout=2)
            await asyncio.sleep(self.FADE_INTERVAL)
```

Integration with TTS pipeline — modify `device/audio/pipeline.py`:

```python
class WM8960Pipeline(AudioPipeline):
    def speak(self, text: str) -> None:
        # Duck music before speaking
        if self._music_ducker and self._is_music_playing():
            self._music_ducker.duck()

        try:
            # ... existing TTS pipeline
            tts = TextToSpeech(player)
            tts.speak(text)
        finally:
            # Restore music after speaking
            if self._music_ducker:
                self._music_ducker.restore()
```

---

## 4. Agent Music Tools

### 4.1 Tool Definitions

Add to `server/agent_tools.py`:

```python
MUSIC_TOOLS = [
    {
        "name": "music_control",
        "description": (
            "Control music playback. Can play, pause, skip, go back, "
            "adjust volume, toggle shuffle/repeat. When playing a specific "
            "song, search for it first with music_search, then use the URI."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["play", "pause", "next", "previous", "volume", "shuffle", "repeat"],
                },
                "uri": {
                    "type": "string",
                    "description": "Spotify URI to play (e.g. spotify:track:xxx). Omit to resume current.",
                },
                "volume": {
                    "type": "integer",
                    "description": "Volume 0-100 (only for action=volume).",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "music_now_playing",
        "description": (
            "Get what's currently playing on Spotify. Returns track name, "
            "artist, album, progress, and duration. Use this when the user "
            "asks 'what's playing?' or you need music context for conversation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "music_search",
        "description": (
            "Search Spotify for tracks, artists, albums, or playlists. "
            "Returns up to 5 results with names, artists, and URIs. "
            "Use the URI with music_control to play a result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (song name, artist, mood, genre).",
                },
                "type": {
                    "type": "string",
                    "enum": ["track", "artist", "album", "playlist"],
                    "description": "What to search for (default: track).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "music_queue",
        "description": (
            "Add a track to the playback queue, or view the current queue. "
            "Use music_search first to get a track URI."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "view"],
                },
                "uri": {
                    "type": "string",
                    "description": "Spotify URI to add (required for action=add).",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "music_recommend",
        "description": (
            "Get music recommendations based on current track, mood, or genre. "
            "Uses Spotify's recommendation engine. Can seed from currently playing "
            "track, specific artists/genres, or the user's taste profile."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "based_on": {
                    "type": "string",
                    "enum": ["current", "mood", "genre", "artist", "history"],
                    "description": "What to base recommendations on.",
                },
                "mood": {
                    "type": "string",
                    "description": "Mood descriptor (e.g. 'chill', 'energetic', 'melancholic'). For based_on=mood.",
                },
                "genre": {
                    "type": "string",
                    "description": "Genre (e.g. 'jazz', 'electronic', 'indie'). For based_on=genre.",
                },
            },
            "required": ["based_on"],
        },
    },
    {
        "name": "music_taste_profile",
        "description": (
            "Get the user's music taste profile. Returns top artists, genres, "
            "listening patterns (time of day, day of week), and recent trends. "
            "Use this to make informed recommendations or discuss music taste."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
```

### 4.2 Now-Playing Context Injection

Add music context to the agent's system prompt via live context (same pattern as weather/tasks).

In `server/main.py` or wherever the system prompt is built:

```python
async def _get_music_context() -> str:
    """Get current music state for system prompt."""
    now_playing = await spotify.get_now_playing()
    if not now_playing or not now_playing.get("is_playing"):
        return ""

    track = now_playing["track"]
    artist = now_playing["artist"]
    album = now_playing["album"]
    progress = now_playing["progress_ms"] // 1000
    duration = now_playing["duration_ms"] // 1000

    return (
        f"[NOW PLAYING] {track} by {artist} ({album}) "
        f"— {progress // 60}:{progress % 60:02d}/{duration // 60}:{duration % 60:02d}"
    )
```

This gives the agent ambient awareness: "I see you're listening to Kind of Blue by Miles Davis."

### 4.3 Mood-to-Music Mapping

For `music_recommend` with `based_on=mood`:

```python
MOOD_TO_SPOTIFY_PARAMS = {
    "chill": {"target_energy": 0.3, "target_valence": 0.5, "target_tempo": 90},
    "energetic": {"target_energy": 0.9, "target_valence": 0.8, "target_tempo": 140},
    "melancholic": {"target_energy": 0.2, "target_valence": 0.2, "target_tempo": 80},
    "focused": {"target_energy": 0.5, "target_valence": 0.4, "target_tempo": 110, "target_instrumentalness": 0.8},
    "happy": {"target_energy": 0.7, "target_valence": 0.9, "target_tempo": 120},
    "angry": {"target_energy": 0.95, "target_valence": 0.3, "target_tempo": 150},
    "romantic": {"target_energy": 0.3, "target_valence": 0.6, "target_tempo": 85},
    "sleepy": {"target_energy": 0.1, "target_valence": 0.4, "target_tempo": 70},
}
```

Uses Spotify's `audio_features` endpoint to tune recommendations by energy, valence, tempo, etc.

---

## 5. Music Logging & Taste Profile

### 5.1 Data Model

New SQLite migration in `device/storage/repository.py` (migration 7):

```sql
CREATE TABLE IF NOT EXISTS listening_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id TEXT NOT NULL,          -- Spotify track ID
    track_name TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    album_name TEXT,
    duration_ms INTEGER,
    played_at REAL NOT NULL,         -- Unix timestamp
    listened_ms INTEGER,             -- How long user actually listened
    skipped INTEGER DEFAULT 0,       -- 1 if skipped before 30s
    source TEXT DEFAULT 'spotify',   -- 'spotify' or 'manual'
    context_type TEXT,               -- 'album', 'playlist', 'artist', 'search'
    context_name TEXT,               -- name of album/playlist/etc
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_listening_history_played
  ON listening_history(played_at DESC);

CREATE INDEX IF NOT EXISTS idx_listening_history_artist
  ON listening_history(artist_name, played_at DESC);

CREATE TABLE IF NOT EXISTS taste_profile (
    key TEXT PRIMARY KEY,            -- e.g. 'top_artists', 'top_genres', 'listening_hours'
    value TEXT NOT NULL,             -- JSON
    updated_at REAL NOT NULL
);
```

### 5.2 Listening Logger

New module: **`server/integrations/music_logger.py`**

```python
class MusicLogger:
    """Tracks listening history and builds taste profile.

    Polls Spotify recently-played API every 60s to log new plays.
    Detects skips (listened < 30s of a track).
    Builds aggregate taste profile periodically.
    """

    def __init__(self, spotify: SpotifyAdapter, db_path: str):
        self._spotify = spotify
        self._db_path = db_path
        self._last_poll_cursor = None  # Spotify 'after' cursor

    async def poll_recent(self):
        """Fetch recently played tracks and log new ones."""
        tracks = await self._spotify.get_recently_played(limit=20)
        for track in tracks:
            if not self._already_logged(track):
                self._log_play(track)

    def _log_play(self, track: dict):
        """Insert a listening event."""
        # track: {track_id, track_name, artist_name, album_name,
        #         duration_ms, played_at, context_type, context_name}

    def build_taste_profile(self) -> dict:
        """Aggregate listening history into taste profile."""
        return {
            "top_artists_30d": self._top_artists(days=30),
            "top_genres_30d": self._top_genres(days=30),
            "total_tracks_30d": self._count(days=30),
            "total_hours_30d": self._total_hours(days=30),
            "listening_by_hour": self._by_hour_of_day(),
            "listening_by_day": self._by_day_of_week(),
            "discovery_rate": self._new_artist_rate(days=30),
            "skip_rate": self._skip_rate(days=30),
            "top_contexts": self._top_playlists(days=30),
        }
```

### 5.3 Agent Taste Awareness

The agent can reference listening data naturally:

- "You've been listening to a lot of jazz this week."
- "You usually listen to ambient music around this time."
- "You've discovered 12 new artists this month."
- "Your skip rate is higher than usual today — not feeling the playlist?"

This context is injected via the `music_taste_profile` tool, called on-demand.

---

## 6. AirPod Mode UX

### 6.1 Mode Detection & Activation

When AirPods connect (detected by `BluetoothAudioManager.connect()` returning success + device type = "airpods"):

1. **Status bar indicator:** Show headphone icon in status bar
2. **LED change:** Set LED to blue pulse (AirPod mode active)
3. **Audio routing:** Switch to `AudioRouter.enter_airpod_mode()`
4. **AVRCP listener:** Start `AVRCPListener` if not already running
5. **Notification:** Toast "AirPods Connected" on device screen

When AirPods disconnect:

1. **Status bar:** Remove headphone icon
2. **LED:** Return to default
3. **Audio routing:** `AudioRouter.exit_airpod_mode()`, switch back to WM8960 speaker
4. **AVRCP listener:** Keep running (no-op without connected device)
5. **Notification:** Toast "AirPods Disconnected"

### 6.2 Audio-First Interaction Flow

With AirPods connected, the interaction model shifts:

```
USER TAPS AIRPOD (Play/Pause) → Device enters recording mode
USER SPEAKS → WM8960 mic captures audio (or AirPod HFP mic if enabled)
USER TAPS AIRPOD AGAIN (Play/Pause) → Recording stops, audio sent to server
SERVER PROCESSES → Agent responds
MUSIC DUCKS → Volume fades to 15%
TTS PLAYS → Agent speech through AirPods
MUSIC RESTORES → Volume fades back to 100%
```

If music is already playing:
- Single tap = pause music (standard behavior)
- Double tap = next track
- Triple tap = previous track
- To talk to agent: use device button (SHORT_PRESS to start recording)

**Conflict resolution:** When music is playing, AirPod taps control music. The device button controls the agent. When no music is playing, AirPod taps can optionally trigger voice input (configurable in settings).

### 6.3 AirPod Battery Level (Best-Effort)

AirPods report battery via Apple's proprietary HFP AT commands. On Linux, this is partially available through BlueZ's Battery Provider:

```python
def get_airpod_battery(address: str) -> dict | None:
    """Try to read AirPod battery from BlueZ Battery1 interface."""
    try:
        result = subprocess.run(
            ["bluetoothctl", "info", address],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if "Battery Percentage" in line:
                pct = int(line.split("(")[-1].rstrip(")").strip(), 16)
                return {"battery_percent": pct}
    except Exception:
        pass
    return None
```

This works for some AirPod models on BlueZ 5.64+. Not reliable enough to depend on, but nice to show when available.

---

## 7. Implementation Plan

### Phase 1: AVRCP Gesture Input (1-2 days)

**Files to create:**
- `device/bluetooth/avrcp_listener.py` — D-Bus MediaPlayer1 monitor with evdev fallback

**Files to modify:**
- `device/main.py` — Wire AVRCP listener into event loop
- `device/screens/base.py` — Add `source` parameter to `handle_action()`
- `device/screens/panels/home.py` — Handle AVRCP events (play/pause = voice input toggle)

**Dependencies:**
- `pip install dbus-next evdev` (add to `requirements-device.txt`)

### Phase 2: Audio Router & AirPod Mode (1-2 days)

**Files to create:**
- `device/bluetooth/audio_router.py` — Routing manager with ducking support

**Files to modify:**
- `device/bluetooth/audio_manager.py` — Add `detect_device_type()`, connection callbacks
- `device/audio/pipeline.py` — Integrate music ducking into `speak()`
- `device/screens/panels/bt_audio.py` — Show AirPod-specific UI when AirPods detected
- `device/power/leds.py` — AirPod mode LED pattern
- `device/screens/components/status_bar.py` — Headphone icon indicator

### Phase 3: Spotify Adapter (2-3 days)

**Files to create:**
- `server/integrations/spotify_adapter.py` — Spotify Web API wrapper
- `server/endpoints/spotify.py` — OAuth callback endpoint, now-playing API

**Files to modify:**
- `server/main.py` — Register Spotify endpoints, add now-playing to live context
- `server/config.py` — SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET env vars
- `.env` — Add Spotify credentials

**Pi setup:**
- Install `spotifyd` binary on Pi
- Create systemd service: `/etc/systemd/system/spotifyd.service`
- Configure: `/home/pi/.config/spotifyd/spotifyd.conf`

### Phase 4: Agent Music Tools (1-2 days)

**Files to modify:**
- `server/agent_tools.py` — Add MUSIC_TOOLS to DEVICE_TOOLS list
- `server/llm_bridge.py` — Handle music tool calls in tool execution loop

**Files to create:**
- `server/integrations/music_tools_handler.py` — Tool call -> SpotifyAdapter dispatch

### Phase 5: Music Logging & Taste Profile (1-2 days)

**Files to create:**
- `server/integrations/music_logger.py` — Polling logger + taste profile builder

**Files to modify:**
- `device/storage/repository.py` — Add migration 7 (listening_history, taste_profile tables)
- `server/heartbeat.py` — Add music polling to heartbeat tick (every 60s)

### Phase 6: Music Player Screen (2-3 days)

**Files to create:**
- `device/screens/panels/music.py` — Now-playing screen with track info, progress, controls
- `device/screens/panels/music_browse.py` — Search, playlists, recommendations

**Files to modify:**
- `device/screens/panels/home.py` — Now-playing widget on home screen
- `device/screens/manager.py` — Register music panel in navigation

### Phase 7: Polish & Edge Cases (1-2 days)

- Auto-reconnect AirPods on boot
- Handle AirPod disconnect during music playback (graceful fallback to speaker)
- Handle Spotify token refresh failure
- "What was that song?" — agent references last 5 songs from listening history
- Wake word through AirPod mic (requires HFP mode toggle)
- Settings: `airpod_mic_mode` (on/off), `music_ducking` (on/off), `auto_airpod_mode` (on/off)

---

## Appendix: Dependency Summary

### Pi Device (requirements-device.txt additions)
```
dbus-next>=0.7.1      # D-Bus async client for AVRCP
evdev>=1.7.0           # Input device fallback for AVRCP
```

### Server (requirements-server.txt additions)
```
spotipy>=2.24.0        # Spotify Web API (or use raw httpx)
```

### System packages (Pi)
```bash
sudo apt install spotifyd          # or manual binary install
sudo apt install playerctl         # debug tool, optional
```

### Spotify Developer Setup
1. Create app at https://developer.spotify.com/dashboard
2. Set redirect URI to `http://bitos.local:8000/spotify/callback`
3. Note Client ID and Client Secret
4. Add to `.env`: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`
5. Complete OAuth flow via `http://bitos.local:8000/spotify/auth`

## Appendix: File Map

```
device/
  bluetooth/
    audio_manager.py      ← existing (modify: device type detection)
    audio_router.py       ← NEW (routing + ducking)
    avrcp_listener.py     ← NEW (gesture capture)
  audio/
    pipeline.py           ← existing (modify: ducking integration)
    player.py             ← existing (no changes needed)
  screens/
    panels/
      bt_audio.py         ← existing (modify: AirPod-specific UI)
      music.py            ← NEW (now-playing screen)
      music_browse.py     ← NEW (search/browse screen)
  storage/
    repository.py         ← existing (modify: migration 7)

server/
  integrations/
    spotify_adapter.py    ← NEW (Spotify Web API)
    music_logger.py       ← NEW (listening history)
    music_tools_handler.py ← NEW (tool dispatch)
  endpoints/
    spotify.py            ← NEW (OAuth + API endpoints)
  agent_tools.py          ← existing (modify: add MUSIC_TOOLS)
  main.py                 ← existing (modify: Spotify init + context)
```
