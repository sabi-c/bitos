# AirPod Gesture Controls for BITOS

**Date:** 2026-03-17
**Status:** Research
**Target:** Pi Zero 2W running BITOS device firmware

## Overview

AirPods (and AirPods Pro) send standard Bluetooth AVRCP (Audio/Video Remote Control Profile) media key events when the user taps, double-taps, triple-taps, or press-and-holds the stems. These events are transport-layer agnostic — any Bluetooth A2DP sink that connects to the AirPods receives them. This document covers how to capture and map those events to BITOS button actions on the Pi Zero 2W.

---

## 1. What AirPods Send Over Bluetooth

AirPods use two Bluetooth profiles when connected:

- **A2DP (Advanced Audio Distribution Profile)** — stereo audio streaming
- **AVRCP (Audio/Video Remote Control Profile)** — media transport controls

When the user performs a gesture, the AirPods firmware translates it into an AVRCP command:

| Gesture | AirPods Gen 2/3 | AirPods Pro (stem squeeze) | AVRCP Command |
|---|---|---|---|
| Single tap / single squeeze | Play/Pause | Play/Pause | `Play` or `Pause` |
| Double tap / double squeeze | Next Track | Next Track | `Next` |
| Triple tap / triple squeeze | Previous Track | Previous Track | `Previous` |
| Long press / long squeeze | Siri (default) / ANC toggle | ANC / Transparency toggle | *No AVRCP event* — handled internally by AirPods firmware |
| Volume up (Pro stem slide) | N/A | Volume up | `VolumeUp` |
| Volume down (Pro stem slide) | N/A | Volume down | `VolumeDown` |

**Key insight:** The tap/squeeze gestures that map to play/pause/next/previous are standard AVRCP commands. They show up on the Linux host like any other Bluetooth media remote. The long-press (Siri/ANC) is handled entirely inside the AirPods firmware and does NOT send an AVRCP event to the connected device.

**Configurable gestures:** On iPhone, users can change what double-tap does (next track, previous track, play/pause, Siri, or off). BITOS cannot control this — it sees whatever AVRCP command the AirPods are configured to send. The default is typically: double-tap = next, triple-tap = previous.

---

## 2. How to Capture AVRCP Events on Linux/Pi

There are four viable approaches, ordered by reliability:

### 2a. D-Bus + BlueZ MediaPlayer1 Interface (Recommended)

BlueZ (the Linux Bluetooth stack) exposes connected media controllers via D-Bus. When AirPods send AVRCP commands, BlueZ processes them and emits D-Bus signals on the `org.bluez.MediaPlayer1` interface.

**How it works:**
1. AirPods connect as A2DP sink
2. BlueZ registers a MediaPlayer1 object at `/org/bluez/hci0/dev_XX_XX_XX_XX_XX_XX/player0`
3. AVRCP commands trigger `PropertiesChanged` signals on the `Status` property (e.g., `playing` -> `paused`)
4. Track change commands trigger changes on `Track` property

**Python implementation using `dbus-next` (async) or `pydbus`:**

```python
import asyncio
from dbus_next.aio import MessageBus
from dbus_next import BusType

BLUEZ_SERVICE = "org.bluez"
MEDIAPLAYER_IFACE = "org.bluez.MediaPlayer1"
PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"

async def monitor_avrcp():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    # Subscribe to all PropertiesChanged on BlueZ objects
    bus.add_message_handler(on_message)

    # Match rule for MediaPlayer1 property changes
    await bus.call(
        bus.introspect(BLUEZ_SERVICE, "/"),
    )

    # Add match for property changes on any BlueZ path
    await bus.add_match_rule(
        "type='signal',"
        "sender='org.bluez',"
        f"interface='{PROPERTIES_IFACE}',"
        f"arg0='{MEDIAPLAYER_IFACE}'"
    )

    await asyncio.Future()  # run forever


def on_message(msg):
    if msg.member != "PropertiesChanged":
        return
    args = msg.body
    if len(args) < 2:
        return
    iface, changed = args[0], args[1]
    if iface != MEDIAPLAYER_IFACE:
        return

    if "Status" in changed:
        status = changed["Status"].value
        # status: "playing", "paused", "stopped"
        handle_play_pause(status)

    if "Track" in changed:
        track = changed["Track"].value
        handle_track_change(track)
```

**Calling MediaPlayer1 methods directly** (to send commands back, or to read state):

```python
# Get the player proxy
introspection = await bus.introspect(BLUEZ_SERVICE, player_path)
proxy = bus.get_proxy_object(BLUEZ_SERVICE, player_path, introspection)
player = proxy.get_interface(MEDIAPLAYER_IFACE)

# Read current status
status = await player.get_status()

# Can also call: player.call_play(), player.call_pause(),
# player.call_next(), player.call_previous()
```

**Pros:** Native BlueZ integration, no extra daemons, works with PulseAudio and PipeWire, async-friendly.
**Cons:** Requires `dbus-next` pip package. MediaPlayer1 object only exists while AirPods are connected and an audio session is active.

### 2b. evdev Input Device (Fallback)

Some Bluetooth audio devices register as HID (Human Interface Device) input devices in addition to A2DP. When they do, AVRCP key events appear as Linux input events readable via `evdev`.

```python
import evdev

# Find the AirPods input device
devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
for dev in devices:
    if "airpods" in dev.name.lower():
        airpods = dev
        break

# Read events
for event in airpods.read_loop():
    if event.type == evdev.ecodes.EV_KEY:
        if event.code == evdev.ecodes.KEY_PLAYPAUSE:
            handle_play_pause()
        elif event.code == evdev.ecodes.KEY_NEXTSONG:
            handle_next()
        elif event.code == evdev.ecodes.KEY_PREVIOUSSONG:
            handle_previous()
        elif event.code == evdev.ecodes.KEY_VOLUMEUP:
            handle_volume_up()
        elif event.code == evdev.ecodes.KEY_VOLUMEDOWN:
            handle_volume_down()
```

**Relevant evdev key codes:**
- `KEY_PLAYPAUSE` (164)
- `KEY_NEXTSONG` (163)
- `KEY_PREVIOUSSONG` (165)
- `KEY_VOLUMEUP` (115)
- `KEY_VOLUMEDOWN` (114)
- `KEY_STOPCD` (166)

**Pros:** Simple, synchronous, well-understood Linux input model.
**Cons:** AirPods may NOT register as an HID device on all BlueZ versions. Whether this works depends on the BlueZ AVRCP passthrough configuration (`uinput` module). Requires root or input group membership.

### 2c. `bluetoothctl` + D-Bus Monitor (Quick and Dirty)

For prototyping, you can monitor BlueZ D-Bus traffic with `dbus-monitor`:

```bash
dbus-monitor --system "interface='org.bluez.MediaPlayer1'" |
while read -r line; do
    case "$line" in
        *"Status"*"playing"*) echo "PLAY" ;;
        *"Status"*"paused"*) echo "PAUSE" ;;
    esac
done
```

Or use `bluetoothctl` interactively to see player status changes. Not suitable for production but useful for debugging.

### 2d. MPRIS / PipeWire Media Session

If PipeWire is running (Pi OS Bookworm default), AVRCP events flow through the MPRIS (Media Player Remote Interfacing Specification) D-Bus interface. The `playerctl` CLI tool can monitor these:

```bash
playerctl --follow status   # prints "Playing" / "Paused" on change
playerctl --follow metadata  # prints track changes
```

Python equivalent using the `mpris-server` or `pydbus` MPRIS interface. This is essentially the same as approach 2a but through the MPRIS abstraction layer.

---

## 3. Mapping AVRCP Events to BITOS Actions

BITOS currently uses a single physical button with these actions:

| Button Pattern | BITOS Action |
|---|---|
| SHORT_PRESS | Next item / scroll |
| DOUBLE_PRESS | Select / confirm |
| LONG_PRESS | Go back |
| TRIPLE_PRESS | Agent overlay / up |
| POWER_GESTURE (5x) | Quick menu |

### Proposed AVRCP-to-BITOS Mapping

| AVRCP Event | BITOS Action | Rationale |
|---|---|---|
| Play/Pause (single tap) | `AIRPOD_PLAY_PAUSE` | Context-dependent: during voice playback = pause/resume TTS; during recording = stop recording; idle = start voice input |
| Next (double tap) | `SHORT_PRESS` | Navigate forward, consistent with "next" semantics |
| Previous (triple tap) | `TRIPLE_PRESS` | Navigate backward/up |
| Volume Up (Pro stem) | Increase device volume by 10 | Direct volume control, bypass navigation |
| Volume Down (Pro stem) | Decrease device volume by 10 | Direct volume control, bypass navigation |

### Alternative: Dedicated AirPod Event Channel

Instead of mapping to existing button actions, create a parallel `AirPodInput` source that the active screen can handle independently:

```python
class InputSource:
    BUTTON = "button"
    AIRPOD = "airpod"

# In screen's handle_action:
def handle_action(self, action: str, source: str = InputSource.BUTTON):
    if source == InputSource.AIRPOD:
        if action == "PLAY_PAUSE":
            self._toggle_voice()  # screen-specific behavior
            return
    # ... existing button handling
```

This gives each screen/panel full control over what AirPod gestures do in context.

---

## 4. Implementation Architecture

### 4.1 New Module: `device/bluetooth/avrcp_listener.py`

```python
"""AVRCP media key listener for Bluetooth audio devices.

Monitors D-Bus for MediaPlayer1 property changes and translates
AVRCP commands into BITOS input events.
"""
import asyncio
import logging
import threading

logger = logging.getLogger(__name__)


class AVRCPListener:
    """Listen for AVRCP media key events from connected BT audio devices."""

    def __init__(self, on_event=None):
        self._on_event = on_event  # callback(event_name: str)
        self._running = False
        self._thread = None

    def start(self):
        """Start listening in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, name="avrcp-listener", daemon=True
        )
        self._thread.start()

    def stop(self):
        self._running = False

    def _run_loop(self):
        """Run asyncio event loop for D-Bus monitoring."""
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._monitor())
        finally:
            loop.close()

    async def _monitor(self):
        # ... D-Bus subscription as shown in section 2a
        pass

    def _emit(self, event: str):
        if self._on_event:
            self._on_event(event)
```

### 4.2 Integration with Device Main Loop

In `device/main.py`, wire the AVRCP listener alongside the existing button input:

```python
from bluetooth.avrcp_listener import AVRCPListener

avrcp = AVRCPListener(on_event=lambda e: input_queue.put(("airpod", e)))
avrcp.start()

# In the main event loop:
while running:
    source, action = input_queue.get()
    active_screen.handle_action(action, source=source)
```

### 4.3 Fallback Chain

1. Try D-Bus `MediaPlayer1` monitoring (primary)
2. Fall back to `evdev` input device scanning
3. If neither works, log warning and disable AirPod gesture input

---

## 5. Dependencies

| Package | Purpose | Pi Zero 2W Compatible | Install |
|---|---|---|---|
| `dbus-next` | Async D-Bus client for MediaPlayer1 | Yes | `pip install dbus-next` |
| `evdev` | Linux input device reading (fallback) | Yes | `pip install evdev` |
| `pydbus` | Sync D-Bus client (alternative) | Yes | `pip install pydbus` |
| `playerctl` | CLI MPRIS monitor (debug only) | Yes | `apt install playerctl` |

**System requirements:**
- BlueZ 5.55+ (Pi OS Bookworm ships 5.66)
- D-Bus system bus running (default on Pi OS)
- User in `bluetooth` group (for D-Bus access without root)

---

## 6. Gotchas and Edge Cases

1. **AirPods must be connected as A2DP sink first.** AVRCP events are only sent over an active A2DP connection. If AirPods are paired but not connected, no events will arrive.

2. **MediaPlayer1 object lifecycle.** The D-Bus object at `/org/bluez/.../player0` only exists while the AirPods have an active media session. The listener must handle the object appearing/disappearing (subscribe to `InterfacesAdded` / `InterfacesRemoved` on the BlueZ ObjectManager).

3. **No long-press event.** AirPods handle long-press internally (Siri or ANC toggle). This cannot be remapped or captured on the Pi side. BITOS's `LONG_PRESS` action has no AirPod equivalent.

4. **iPhone configuration affects what BITOS sees.** If the user changes double-tap from "Next Track" to "Siri" in iPhone Bluetooth settings, BITOS will stop receiving the Next event. BITOS cannot detect or override this. Consider a setup hint: "Set AirPods double-tap to Next Track for best experience."

5. **Debouncing.** Single tap generates Play then Pause (or vice versa) rapidly. The listener should debounce: if Play and Pause arrive within 100ms, treat as a single toggle event.

6. **Multiple audio sources.** If AirPods are connected to both iPhone and Pi (AirPods support seamless switching), the AVRCP events go to whichever device currently has the audio session. The Pi must be actively streaming audio (even silence) to maintain the A2DP session.

7. **Volume events on non-Pro models.** Only AirPods Pro (with stem squeeze) send volume AVRCP events. AirPods Gen 2/3 do not have hardware volume controls — volume is controlled via the connected device's UI.

8. **BlueZ AVRCP passthrough.** By default, BlueZ may consume AVRCP events internally (adjusting PulseAudio/PipeWire volume and transport state) rather than forwarding them to applications. To get raw events, you may need to configure BlueZ's `input.conf`:
   ```ini
   # /etc/bluetooth/input.conf
   [General]
   UserspaceHID=true
   ```
   Or listen at the PulseAudio/PipeWire level where the events have already been processed (status changes still visible via D-Bus).

9. **Pi Zero 2W Bluetooth chip.** The BCM43436s supports Bluetooth 4.2 + BLE. A2DP and AVRCP work fine. No Bluetooth 5.0 features (like LE Audio) but AirPods' AVRCP is classic Bluetooth, not BLE.

---

## 7. Recommendations

1. **Start with D-Bus MediaPlayer1 monitoring** (approach 2a). It's the most reliable and does not require extra daemons. Use `dbus-next` for async compatibility with the existing BITOS event loop.

2. **Create a dedicated `AirPodInput` source** rather than mapping directly to button actions. This gives screens the flexibility to handle AirPod gestures contextually (e.g., play/pause means different things on the chat screen vs. the music screen vs. the home screen).

3. **Add a setup step** in the wizard or settings that detects AirPod connection and shows a hint about configuring double-tap to "Next Track" on iPhone.

4. **Implement volume events first** (AirPods Pro) since they are the simplest to handle and most immediately useful — direct volume control without needing the physical button.

5. **Keep the evdev fallback** for robustness. Some BlueZ configurations expose AVRCP as input events by default, and evdev is simpler to debug.

6. **Log AVRCP events** to the device log at DEBUG level for field testing. AirPod gesture timing varies and real-world debouncing thresholds need tuning.
