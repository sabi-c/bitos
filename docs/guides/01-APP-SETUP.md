# Connecting the Open Interpreter 01 App to BITOS

**Date:** 2026-03-16
**Status:** Setup guide — follow these steps to connect the 01 app to your BITOS server.

---

## Overview

The Open Interpreter 01 app is a voice-interface client that can connect to a backend server. There are two versions:

1. **01 Light (React Native app)** — Cross-platform, connects via LiveKit/WebRTC, uses QR code pairing. Available on App Store and Google Play.
2. **Native iOS client** — Simpler, connects via raw WebSocket, manual server URL entry. Available via TestFlight.

For BITOS, the **native iOS client** is the better fit because it uses a plain WebSocket connection that can point directly at the BITOS server. The React Native app requires a LiveKit server, which adds unnecessary complexity.

> **Current state:** BITOS does not yet implement the 01 Light Server WebSocket protocol. A compatibility endpoint (`/ws/01` or adapting `/ws/voice`) needs to be built first. This guide documents the full setup so everything is ready once that endpoint ships. See the protocol section below for what needs to happen server-side.

---

## Part 1: iPhone Setup (Native iOS Client)

### Download

The native iOS 01 client is available via **TestFlight** (Apple's beta testing platform):

**TestFlight link:** https://testflight.apple.com/join/v8SyuzMT

1. Open the link on your iPhone in Safari
2. If you don't have TestFlight installed, the App Store will prompt you to install it first
3. Once TestFlight is installed, tap "Accept" to join the beta
4. Install the "01" app from within TestFlight

> **Note:** The App Store listing at `apps.apple.com/us/app/01-light/id6504464625` returns a 404. The correct App Store ID for the React Native version is `6601937732` (https://apps.apple.com/ca/app/01-light/id6601937732), but that app uses LiveKit, not direct WebSocket. Stick with the TestFlight native client.

### Configure Server URL

1. Open the 01 app
2. Tap the **gear icon** (settings)
3. Enter your BITOS server WebSocket address:
   ```
   ws://YOUR_SERVER_IP:8000/ws/01
   ```
   For example, if your Mac mini is at `192.168.1.50`:
   ```
   ws://192.168.1.50:8000/ws/01
   ```
4. The connection indicator (arrow icon) shows:
   - **Green** = connected
   - **Red** = disconnected
5. Tap the arrow icon to manually reconnect if needed

### Network Requirements

**Same WiFi (simplest):**
- iPhone and BITOS server must be on the same local network
- No port forwarding needed
- Use the server's local IP address (find it with `ipconfig getifaddr en0` on the Mac mini)

**Different networks (Tailscale recommended):**
- Install Tailscale on both the Mac mini and iPhone
- Use the Tailscale IP address (100.x.x.x) as the server address:
  ```
  ws://100.x.x.x:8000/ws/01
  ```
- No port forwarding, no firewall changes, encrypted by default

**Port forwarding (not recommended):**
- Exposes the server to the internet
- The 01 protocol has no authentication — anyone could connect
- If you must: forward port 8000 TCP on your router to the Mac mini's local IP

### Expected Behavior

Once connected:
1. Tap and hold the yellow circle button to speak
2. Release to send audio to BITOS
3. BITOS processes your speech (STT → agent pipeline → TTS)
4. Audio response plays back through the phone speaker
5. Tap the terminal icon to see server responses as text

---

## Part 2: Android Mini Phone Setup

Tested targets:
- **3" Android phone** (e.g., Unihertz Jelly Star, Android 12+)
- **Bluefox NX1** (Android 15)

### Install the App

**Option A: Google Play Store**

The 01 React Native app is on the Play Store:
- Search for "01 Light" by Open Interpreter
- Package: `com.interpreter.app`
- Direct link: https://play.google.com/store/apps/details?id=com.interpreter.app

> **Important:** This is the LiveKit-based React Native app, not the WebSocket-based native client. It requires scanning a QR code from a LiveKit server, which makes it harder to use with BITOS directly. See the workaround below.

**Option B: Sideload the Native Client APK (preferred for BITOS)**

The native iOS client has no Android equivalent. However, you can build the React Native app from source and modify it to use direct WebSocket:

1. Clone the repo: `git clone https://github.com/OpenInterpreter/01-app.git`
2. Install deps: `cd 01-app/app && bun install`
3. Modify `app/screens/LoginScreen.tsx` to hardcode your BITOS server URL
4. Build: `bun android` (requires Android SDK)
5. Install the resulting APK via `adb install`

**Option C: Use the Play Store app with LiveKit (more complex)**

If using the stock Play Store app:
1. You need to run a LiveKit server alongside BITOS
2. Start with: `poetry run 01 --server livekit --expose --qr`
3. Scan the QR code from the app
4. This is heavier infrastructure — only use this if the native approach isn't viable

### Configure Server URL

**For the Play Store app:**
- The app connects by scanning a QR code, not manual URL entry
- The QR code encodes: `{"livekit_server": "wss://your-server-url"}`
- You need the 01 server running with `--expose --qr` to generate this code

**For a modified/sideloaded build:**
- Edit `LoginScreen.tsx` to point at your BITOS server
- Or add a settings screen with manual WebSocket URL entry

### Small Screen Considerations

On a 3" phone (480x854 or similar):

1. **Enable Wearable Mode** in the app settings (gear icon) — this makes the speak button full-screen, ideal for small screens
2. **Increase touch target size** — the default UI is designed for normal phones; wearable mode fixes this
3. **Font scaling** — Go to Android Settings → Display → Font size → set to Default or Small
4. **DPI adjustment** — In Developer Options, set "Smallest width" to 320dp for better layout on tiny screens

### Set as Default Launcher / Always-On App

**Method 1: Screen Pinning (quick, no root)**
1. Open Settings → Security → Screen pinning (or App pinning)
2. Enable it
3. Open the 01 app
4. Open Recent Apps, tap the app icon → "Pin this app"
5. The phone is now locked to the 01 app (unpin with Back + Recents buttons)

**Method 2: Kiosk Mode with ADB (better for permanent setup)**
```bash
# Set the app as the device owner (must be the only account on the device)
adb shell dpm set-device-owner com.interpreter.app/.DeviceAdminReceiver

# Or use a kiosk launcher app like "Fully Kiosk Browser" or "SureLock"
```

**Method 3: Custom Launcher**
1. Install a single-app launcher like "KioskSimple" or "SureLock" from the Play Store
2. Configure it to only allow the 01 app
3. Set it as the default launcher

**Method 4: Replace the launcher (root required)**
```bash
# Using ADB
adb shell cmd package set-home-activity com.interpreter.app/.MainActivity
```

### Keep Screen On
```bash
# Via ADB — keep screen awake while charging
adb shell settings put global stay_on_while_plugged_in 3
```

Or in the app: Android Settings → Developer Options → Stay awake (when charging).

---

## Part 3: BITOS Server Setup

### Current State

BITOS runs on port **8000** by default (configurable via `SERVER_PORT` env var). The server already has:
- `/ws/voice` — WebSocket for device audio streaming (existing BITOS protocol)
- `/ws/blob` — WebSocket for blob gesture events

What's **needed** for 01 app compatibility:
- A `/ws/01` (or `/ws/01-compat`) endpoint that speaks the 01 Light Server protocol
- A `GET /ping` endpoint returning `"pong"` (health check the 01 clients expect)

### 01 Light Server Protocol

The protocol is simple JSON control messages + raw PCM audio bytes on a single WebSocket:

```
Client → Server:
  {"role": "user", "type": "audio", "format": "bytes.raw", "start": true}
  [raw 16-bit PCM bytes, 16kHz, mono]
  {"role": "user", "type": "audio", "format": "bytes.raw", "end": true}

Server → Client:
  {"role": "assistant", "type": "audio", "format": "bytes.wav", "start": true}
  [raw 16-bit PCM bytes, 24kHz, mono]
  {"role": "assistant", "type": "audio", "format": "bytes.wav", "end": true}
```

Audio specs:
- **Input:** 16-bit PCM, 16kHz sample rate, mono, raw bytes (no WAV header)
- **Output:** 16-bit PCM, 24kHz sample rate, mono, raw bytes (no WAV header)

### Environment Variables

In your `.env` file on the BITOS server:

```bash
# Server binding
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Required for the agent pipeline
ANTHROPIC_API_KEY=sk-ant-...

# Client connection URL (for device configs)
BITOS_SERVER_URL=http://YOUR_SERVER_IP:8000
```

### Firewall / Network Config

**macOS firewall (Mac mini):**
```bash
# Check if firewall is enabled
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# If enabled, allow Python through
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/local/bin/python3
```

**Verify the server is accessible from another device:**
```bash
# On the Mac mini — confirm it's listening
lsof -i :8000

# From the phone's network — test with curl (or browser)
curl http://YOUR_SERVER_IP:8000/ping
# Expected response: "pong"
```

**Tailscale (recommended for reliability):**
```bash
# Install on Mac mini
brew install tailscale
sudo tailscaled &
tailscale up

# Install on iPhone: App Store → Tailscale
# Install on Android: Play Store → Tailscale
# All devices join the same Tailnet — use 100.x.x.x addresses
```

### Verify the Connection

1. Start the BITOS server:
   ```bash
   cd /Users/seb/bitos && python -m server.main
   ```

2. Check the health endpoint:
   ```bash
   curl http://localhost:8000/ping
   # Should return: pong
   ```

3. Test WebSocket connectivity (from another machine):
   ```bash
   # Using websocat (brew install websocat)
   websocat ws://YOUR_SERVER_IP:8000/ws/01
   # Type a JSON message to test:
   # {"role": "user", "type": "audio", "format": "bytes.raw", "start": true}
   ```

4. Open the 01 app on the phone, enter the server URL, and check the connection indicator turns green.

---

## Part 4: Troubleshooting

### Connection Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| App shows red connection indicator | Server unreachable | Check IP address, confirm same WiFi or Tailscale connected |
| "Connection refused" | Server not running or wrong port | Verify server is running: `lsof -i :8000` |
| Connects then immediately disconnects | Protocol mismatch | Check BITOS server logs for WebSocket errors; ensure `/ws/01` endpoint exists |
| Works on WiFi, fails on cellular | Not on same network | Use Tailscale, or set up port forwarding |
| Timeout after a few seconds | Firewall blocking | Check macOS firewall settings (see above) |

### Audio Not Working

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No audio captured | Mic permission denied | Check phone Settings → 01 app → Microphone permission |
| Audio sent but no response | STT failing server-side | Check BITOS server logs for transcription errors |
| Response text appears but no audio | TTS failing or audio format mismatch | Verify TTS is configured; check sample rate (24kHz output expected) |
| Audio playback is garbled/choppy | Sample rate mismatch | Ensure server sends 16-bit PCM at 24kHz mono |
| Echo or feedback | Speaker audio picked up by mic | Use push-to-talk mode (not voice activity detection) |

### Server Not Responding

```bash
# Check if the server process is running
ps aux | grep "server.main"

# Check server logs for errors
tail -f /Users/seb/bitos/logs/server.log

# Restart the server
cd /Users/seb/bitos && python -m server.main

# Check if the port is already in use
lsof -i :8000
```

### Android-Specific Issues

| Symptom | Fix |
|---------|-----|
| App crashes on small screen | Enable Wearable Mode in settings |
| Battery optimization kills the app | Settings → Battery → 01 app → "Don't optimize" |
| WiFi drops when screen off | Settings → WiFi → Advanced → Keep WiFi on during sleep: Always |
| QR scanner won't focus (3" screen) | Hold phone ~6 inches from QR code; ensure good lighting |

### iPhone-Specific Issues

| Symptom | Fix |
|---------|-----|
| TestFlight says "beta expired" | Check for an updated build in TestFlight; betas expire after 90 days |
| No sound output | Check iPhone silent switch; check volume; try with headphones |
| App suspended in background | iOS aggressively suspends apps; keep the app in foreground |

---

## Implementation TODO

Before this guide is fully usable, the BITOS server needs:

- [ ] `GET /ping` endpoint returning `"pong"`
- [ ] `WebSocket /ws/01` endpoint implementing the 01 Light Server audio protocol
- [ ] Audio pipeline: receive 16kHz PCM → STT → agent → TTS → send 24kHz PCM
- [ ] Test with the native iOS TestFlight client
- [ ] Test with the React Native Play Store app (if LiveKit path is pursued)

See `/Users/seb/bitos/docs/planning/OPEN_INTERPRETER_INTEGRATION.md` for the full integration analysis and protocol details.
