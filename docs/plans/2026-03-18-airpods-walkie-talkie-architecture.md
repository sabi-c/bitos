# AirPods Walkie-Talkie Architecture

> Captured 2026-03-18. Core insight: AirPods don't need custom hardware — they talk to whatever they're paired to. The intelligence lives on the Mac mini, the interface lives in your ears.

---

## The Core Loop

```
You wear AirPods
         ↓
   Single tap stem
         ↓
Mac mini detects media key (pynput)
         ↓
FastAPI starts recording from AirPods mic (sounddevice, device="AirPods")
         ↓
You talk
         ↓
Single tap again → stops recording
         ↓
STT → agent processes → TTS
         ↓
Audio plays back through AirPods
         ↓
Watch face shows state (blob breathing / pulsing / speaking)
```

No new hardware required for the core loop. The watch face is an aesthetic/usability layer on top.

---

## Path A — AirPods → Mac mini (Fastest, Zero Hardware)

Mac mini is always on. AirPods connect to it. Stem press fires macOS media key events. Python daemon intercepts:

```python
from pynput import keyboard

def on_press(key):
    if key == keyboard.Key.media_play_pause:
        trigger_walkie_talkie_start()  # single stem press
    elif key == keyboard.Key.media_next:
        trigger_walkie_talkie_stop()   # double press

with keyboard.Listener(on_press=on_press) as listener:
    listener.join()
```

Audio comes back through AirPods automatically since they're the active output device. Works today.

## Path B — AirPods → XS19 Pro (LTE Mobility)

Same concept on Android. App on XS19 intercepts media button events, sends webhook to Mac mini. XS19 has Mint Mobile LTE. AirPods audio routes through it. Already owned, zero new hardware.

---

## Option A — iPhone App (Fastest Software Path)

iPhone connects to Mac mini over internet. AirPods connect to iPhone normally. App intercepts stem press:

```swift
let commandCenter = MPRemoteCommandCenter.shared()
commandCenter.togglePlayPauseCommand.addTarget { event in
    self.toggleWalkieTalkie()
    return .success
}
```

Audio recording from AirPods mic, playback through AirPods, WebSocket to Mac mini — all standard iOS APIs. Buildable in a weekend with SwiftUI + URLSessionWebSocketTask.

**Limitation:** when app is backgrounded, iOS reclaims controls. Only reliable when app is active. Background audio sessions help but fiddly.

## Option B — Standalone Device (Full Control)

Small device in pocket/bag. AirPods pair to it instead of iPhone. Connects to Mac mini over LTE. 100% control — no OS interference, no Siri fighting for the button.

### Hardware options (simplest first):

1. **XS19 Pro** — already owned. Minimal Android app. Mint Mobile SIM. WebSocket to Mac mini. Zero new hardware.
2. **Luckfox Lyra Pi with LTE** (~$70) — runs Linux, full BITOS code, LTE baked in
3. **ESP32 + SIM7670** — most compact. BT A2DP sink/source + LTE. Hardest to build, smallest result.

---

## The Watch-Face Display

The ideal display surface. Device becomes: **show me what state I'm in**.

**Waveshare ESP32-S3 AMOLED 2.06" Watch Dev Board (~$35)**
- 2.06" AMOLED capacitive touchscreen, 410×502
- 6-axis IMU, dual digital mics, ES8311 audio codec, battery support
- ESP32-S3R8, 8MB PSRAM, 32MB flash, BT 5 LE
- Watch form factor with case
- No cellular — connects via WiFi to Mac mini, or XS19 hotspot for LTE

BITOS blob on a watch face. Shows: listening / thinking / speaking state. Glance at wrist instead of pulling out a device.

---

## Cellular Connectivity (for ESP32 watch)

Don't need cellular on the watch itself. Need the connection alive away from home WiFi:

1. **XS19 Pro hotspot** — already owned, Mint Mobile SIM, ESP32 joins it. Done.
2. **iPhone hotspot** — personal hotspot, ESP32 joins automatically.
3. **Luckfox Lyra Pi with LTE** — if you want single device instead of watch + phone.

---

## What To Build Next

### This week (zero hardware):
`pip install pynput` on Mac mini. Write media key listener. Test: AirPods stem → start recording → STT → agent → TTS → playback through AirPods. That's the whole loop.

### Next:
Get Waveshare AMOLED watch board (~$35). Show blob state over WiFi. Wear on wrist.

### Later:
Swap watch WiFi for XS19 hotspot for full LTE mobility.

---

## Decision Tree

```
Want it working THIS WEEK?
  → Path A: AirPods → Mac mini + pynput listener

Want mobile (away from home)?
  → Already have iPhone? Option A: iOS app (weekend build)
  → Want full control? Option B: XS19 Pro as dedicated BT host

Want the watch face?
  → Waveshare ESP32-S3 AMOLED ($35) over WiFi
  → LTE via XS19 hotspot when mobile
```

The Mac mini server side stays identical in ALL cases. Just changing the client. Server doesn't care if it's talking to pynput, an iPhone, a Pi, or an ESP32 — all WebSocket audio streams.
