# LibrePods / AirPods Gesture Detection & Bluetooth Connection Manager

**Date:** 2026-03-17
**Status:** Deep Research — Design-Ready
**Hardware:** Pi Zero 2W, BCM43436s (BLE 4.2 + Classic BT), 240x280 OLED

---

## Part 1: AirPods Gesture Detection on Linux

### The Core Problem

On Linux/BlueZ, AirPods Pro 2 tap gestures (single, double, triple press on stem) all emit the same AVRCP passthrough command: `KEY_PLAYCD` (XF86AudioPlay). There is no distinction at the uinput layer. This is a confirmed, unresolved issue (Arch Linux forums, June 2024). The gestures work correctly on Android and iOS because those platforms use Apple's proprietary AAP (Apple Accessory Protocol) over L2CAP rather than relying on AVRCP.

**Why it happens:** AirPods handle gesture-to-action mapping internally. On Apple/Android, the AirPods send AAP packets that describe which action was triggered (single=0x05, double=0x06, triple=0x07, long=0x08). On Linux without AAP support, the AirPods fall back to AVRCP passthrough for basic play/pause, but the firmware collapses all tap types into a single AVRCP PLAY command.

### LibrePods Project

**Repo:** github.com/kavishdevar/librepods
**Languages:** C++/QML (Linux), Kotlin (Android), Python (hearing aid helper)
**License:** Open source

#### What LibrePods Actually Does on Linux

| Feature | Linux Support | Notes |
|---------|:---:|-------|
| Noise control (Off/ANC/Transparency/Adaptive) | Yes | Via AAP L2CAP packets |
| Battery monitoring | Yes | AAP + BLE advertisement parsing |
| Ear detection (auto-pause) | Yes | AAP ear detection packets |
| Conversational awareness | Yes | Toggle via AAP |
| Head gesture detection (nod/shake) | **No** | Android-only, requires sensor API |
| Stem press detection (single/double/triple/long) | **No** | Android-only, parsed from AAP stream |
| Stem press action customization | **No** | Android-only |
| Hearing aid / audiogram | Partial | Separate Python script, raw L2CAP sockets |
| Media controls (play/pause/skip) | Yes | Via AVRCP (system-level, not AAP) |

**Critical finding:** LibrePods on Linux does NOT currently solve the tap gesture problem. The stem press detection (with distinct single/double/triple/long identification) exists only in the Android codebase (`GestureDetector.kt`), which parses AAP sensor data packets streaming over L2CAP. The Linux C++ implementation lacks this feature.

**However**, the AAP protocol knowledge exists in the project. The protocol is fully documented, and the Android implementation proves that distinct tap types can be read from the AAP data stream.

#### LibrePods Linux Dependencies

- Qt6 (base, connectivity, multimedia, declarative)
- OpenSSL dev headers
- PulseAudio dev libraries
- CMake

Build: `mkdir build && cd build && cmake .. && make -j$(nproc)`

### AAP Protocol Details (from LibrePods reverse engineering)

**Transport:** L2CAP, PSM 0x1001 (4097)

**Handshake (mandatory, 3 phases):**
1. `HANDSHAKE` -> `HANDSHAKE_ACK`: `00 00 04 00 01 00 02 00 00 00 00 00 00 00 00 00`
2. `SET_SPECIFIC_FEATURES` -> `FEATURES_ACK`: `04 00 04 00 4d 00 ff 00 00 00 00 00 00 00`
3. `REQUEST_NOTIFICATIONS` -> metadata: `04 00 04 00 0F 00 FF FF FF FF`

**Key packet formats:**

| Feature | Header | Data |
|---------|--------|------|
| Battery | `04 00 04 00 04 00` | `[count] ([component] 01 [level] [status] 01)...` |
| Ear detection | `04 00 04 00 06 00` | `[primary] [secondary]` (0x00=in, 0x01=out, 0x02=case) |
| Noise control | `04 00 04 00 09 00 0D` | `[mode] 00 00 00` (01=off, 02=ANC, 03=transp, 04=adaptive) |
| Conv. awareness | `04 00 04 00 4B 00` | `02 00 01 [level]` |
| Head tracking | `04 00 04 00 17 00` | Orientation (3x2B @ offset 43) + Accel (2x2B @ offset 51) |

**Stem press identifiers (from Android AAP parsing):**

| Press Type | Byte Value |
|-----------|-----------|
| Single | 0x05 |
| Double | 0x06 |
| Triple | 0x07 |
| Long press | 0x08 |

### Approach 1: Port AAP Stem Press Detection to Python (RECOMMENDED)

**Strategy:** Open a raw L2CAP socket to PSM 0x1001, perform the AAP handshake, subscribe to notifications, and parse incoming packets for stem press events.

**Why this is viable:**
- The protocol is fully documented in LibrePods
- L2CAP sockets work on Linux (Python `socket` module with `BTPROTO_L2CAP`)
- The Android code proves the packet format for tap detection
- No kernel patches or BlueZ modifications needed

**Implementation sketch:**

```python
import socket
import struct

# L2CAP connection to AirPods
sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
sock.connect((AIRPODS_MAC, 0x1001))  # PSM 0x1001

# Send handshake
sock.send(bytes.fromhex("00000400010002000000000000000000"))
ack = sock.recv(256)

# Enable features
sock.send(bytes.fromhex("0400040004d00ff00000000000000"))
ack = sock.recv(256)

# Subscribe to notifications
sock.send(bytes.fromhex("040004000F00FFFFFFFF"))

# Parse incoming packets
while True:
    data = sock.recv(1024)
    # Parse for stem press events (0x05-0x08)
    # Parse for ear detection, battery, etc.
```

**Work required:**
1. Study LibrePods Android `GestureDetector.kt` to identify exact packet offset for stem press byte
2. Implement AAP handshake in Python
3. Build async packet parser (integrate with asyncio event loop)
4. Map press types to BITOS actions

**Risk:** The exact packet offset for stem press events needs to be confirmed by packet capture or by reading the Android source more carefully. The AAP Definitions doc doesn't explicitly document the stem press notification packet format, but the Android code parses it from the AAP stream.

### Approach 2: AVRCP Timing Heuristic (FALLBACK)

Since all taps produce `KEY_PLAYCD`, we could try to distinguish them by timing:

- Single tap: one KEY_PLAYCD, no follow-up within 400ms
- Double tap: two KEY_PLAYCD events within 400ms
- Triple tap: three KEY_PLAYCD events within 400ms

**Implementation:** Use `evdev` (Python) or `evsieve` to monitor `/dev/input/eventX` for the AVRCP device.

```python
import asyncio
import evdev

async def monitor_taps(device_path):
    device = evdev.InputDevice(device_path)
    tap_times = []
    WINDOW = 0.4  # 400ms window

    async for event in device.async_read_loop():
        if event.type == evdev.ecodes.EV_KEY and event.code == evdev.ecodes.KEY_PLAYCD:
            if event.value == 1:  # key press
                tap_times.append(event.timestamp())
                await asyncio.sleep(WINDOW)
                count = len([t for t in tap_times if event.timestamp() - t < WINDOW])
                tap_times.clear()
                if count == 1:
                    handle_single_tap()
                elif count == 2:
                    handle_double_tap()
                elif count >= 3:
                    handle_triple_tap()
```

**Problems with this approach:**
- **Unconfirmed:** We don't know if AirPods actually send multiple AVRCP events for multi-tap, or if the firmware sends a single event after processing the gesture internally. The Arch Linux forum post suggests all taps produce the same single event, meaning timing heuristics won't help.
- **400ms latency** on every single tap (waiting to see if more taps follow)
- Fragile and model-dependent

**Verdict:** This is a fallback only if AAP parsing proves too difficult. Test first by running `evtest` and doing single/double/triple taps to see if multiple events arrive.

### Approach 3: Audio Click Detection (EXPERIMENTAL)

AirPods produce a subtle click sound in the audio stream when the stem is pressed. Theoretically, we could detect this by analyzing the microphone input for characteristic click patterns.

**Challenges:**
- The click may not be present in the SCO/HFP audio stream
- Click detection requires real-time audio DSP with very low latency
- Distinguishing clicks from ambient noise is unreliable
- Multiple clicks for double/triple would need sub-200ms timing resolution

**Verdict:** Not recommended. Too fragile, too much DSP overhead for Pi Zero 2W, and the click may not even be present in the audio data accessible to the host.

### Approach 4: BNO085 IMU as Bridge Gesture Input ($12)

**Product:** Adafruit BNO085 breakout (STEMMA QT / Qwiic)
**Interface:** I2C (400kHz recommended) or UART-RVC mode
**Library:** `adafruit-circuitpython-bno08x`

**Built-in gesture features:**
| Feature | Status | Notes |
|---------|--------|-------|
| Shake detector | Built-in | Hardware-level, reliable |
| Tap detector | Listed but unsupported | In Adafruit library, not implemented |
| Stability classification | Built-in | "On table" / "Stable" / "Motion" |
| Activity classification | Built-in | Walking, running, still, etc. |
| Step detector | Built-in | |
| Rotation vector | Built-in | Full quaternion orientation |

**Nod/shake detection (custom, using rotation vector):**

```python
import board
import busio
from adafruit_bno08x.i2c import BNO08X_I2C
from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR

i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
bno = BNO08X_I2C(i2c)
bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)

# Track pitch (nod) and yaw (shake) changes over time
prev_pitch = 0
NOD_THRESHOLD = 15  # degrees
SHAKE_THRESHOLD = 20  # degrees

while True:
    quat = bno.quaternion  # (i, j, k, real)
    # Convert to Euler angles, detect rapid pitch changes (nod)
    # or rapid yaw oscillation (shake)
```

**Use case for BITOS:** Mount the BNO085 on the device body (not the AirPods). Detect:
- Nod = "yes" / confirm / accept call
- Shake = "no" / dismiss / reject call
- Tilt = scroll / navigate
- Tap on device = select (via built-in shake detector as proxy)

**Cost:** ~$12 for the breakout board
**Wiring:** 4 pins (VIN, GND, SDA, SCL) to Pi Zero 2W I2C bus

**Verdict:** Good complementary input, but does NOT solve the AirPods tap detection problem. This detects device body gestures, not AirPod stem taps. Useful for additional interaction modality.

### Approach 5: D-Bus Monitoring for Granular AVRCP Events

**What's available at D-Bus level:**

BlueZ exposes AVRCP through several D-Bus interfaces:
- `org.bluez.MediaControl1` — basic play/pause/stop/next/prev
- `org.bluez.MediaPlayer1` — track info, position, status
- `org.freedesktop.DBus.Properties` — PropertiesChanged signals

**Monitoring command:**
```bash
dbus-monitor --system "type='signal',sender='org.bluez'" | grep -A5 MediaPlayer
```

**Reality:** The D-Bus layer sits above the uinput layer. BlueZ processes AVRCP passthrough commands, maps them to uinput key events, and separately updates MediaPlayer1 properties. The granularity is the same as what evtest shows — there is no hidden richer event stream at the D-Bus level for AirPods taps. The tap type distinction happens inside the AirPods firmware and is communicated via AAP, not AVRCP.

### Recommended Strategy

**Primary: AAP L2CAP parsing (Approach 1)**

1. Port the LibrePods AAP handshake and notification subscription to Python
2. Parse the AAP stream for stem press events (bytes 0x05-0x08)
3. Also get battery, ear detection, noise control for free
4. Run as an async service alongside the BT connection manager

**Secondary: BNO085 IMU (Approach 4)**

1. Add as complementary input for device-body gestures
2. Nod/shake for yes/no in agent conversations
3. $12 hardware cost, simple I2C wiring

**Discard: AVRCP timing, audio click detection, D-Bus monitoring**

---

## Part 2: Bluetooth Connection Manager / Pairing Wizard

### Architecture Overview

```
+---------------------------+
|    BITOS BT Manager       |
|  (Python async service)   |
+---------------------------+
|                           |
|  +---------------------+ |
|  | Classic BT Manager  | |    <-- A2DP sink, AVRCP, HFP
|  | (BlueZ D-Bus)       | |
|  +---------------------+ |
|                           |
|  +---------------------+ |
|  | BLE GATT Server     | |    <-- Companion app pairing
|  | (existing)          | |
|  +---------------------+ |
|                           |
|  +---------------------+ |
|  | AAP Client          | |    <-- AirPods features (Part 1)
|  | (L2CAP raw socket)  | |
|  +---------------------+ |
|                           |
|  +---------------------+ |
|  | Pairing Wizard UI   | |    <-- OLED display flow
|  | (display events)    | |
|  +---------------------+ |
+---------------------------+
         |
    D-Bus System Bus
         |
+---------------------------+
|      BlueZ daemon         |
+---------------------------+
         |
+---------------------------+
|   BCM43436s (HCI)         |
|   BLE 4.2 + Classic BT   |
+---------------------------+
```

### Python Library Recommendations

#### Winner: `dbus-next` (async D-Bus) + raw sockets

| Library | Pros | Cons | Verdict |
|---------|------|------|---------|
| **dbus-next** | Pure Python, async/await native, well-maintained, no C deps | Lower-level than bluezero | **Use this** |
| **bluezero** | High-level API, good docs, Pi-focused | Sync-only (GLib main loop), less control | Good for prototyping |
| **pybluez2** | Direct HCI access | Requires C compilation, less maintained | Skip |
| **dasbus** | Clean D-Bus bindings | Less community adoption | Alternative to dbus-next |
| **bluez-peripheral** | BLE GATT server helper | BLE only, no Classic BT | Already using similar |

**Recommendation:** Use `dbus-next` for all BlueZ D-Bus interactions (discovery, pairing, connection management, profile monitoring). Use Python `socket` with `BTPROTO_L2CAP` for the AAP client (no library needed).

### BlueZ D-Bus Interfaces for BT Management

```
org.bluez.Adapter1          — scan, discoverable, powered
org.bluez.Device1           — pair, trust, connect, disconnect, properties
org.bluez.AgentManager1     — register pairing agent
org.bluez.Agent1            — handle pairing requests (PIN, confirm)
org.bluez.MediaControl1     — AVRCP basic controls
org.bluez.MediaPlayer1      — track info, playback status
org.bluez.MediaTransport1   — audio transport state, codec, volume
```

### Connection Manager Implementation

```python
import asyncio
from dbus_next.aio import MessageBus
from dbus_next import BusType

class BTConnectionManager:
    """Manages Bluetooth connections via BlueZ D-Bus interface."""

    RECONNECT_INTERVAL = 5.0      # seconds between reconnect attempts
    RECONNECT_MAX_BACKOFF = 60.0   # max backoff
    SCAN_TIMEOUT = 30.0            # discovery timeout for wizard

    def __init__(self):
        self.bus = None
        self.adapter = None
        self.known_devices = {}     # mac -> DeviceState
        self.connected_audio = None # currently connected audio device
        self._reconnect_tasks = {}

    async def start(self):
        self.bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

        # Get adapter
        introspect = await self.bus.introspect("org.bluez", "/org/bluez/hci0")
        obj = self.bus.get_proxy_object("org.bluez", "/org/bluez/hci0", introspect)
        self.adapter = obj.get_interface("org.bluez.Adapter1")

        # Register NoInputNoOutput agent for headless pairing
        await self._register_agent()

        # Monitor for device property changes (connect/disconnect)
        self.bus.add_message_handler(self._on_dbus_signal)

        # Attempt reconnect to trusted audio devices
        await self._reconnect_trusted()

    async def _register_agent(self):
        """Register a pairing agent that auto-accepts for audio devices."""
        # Implement org.bluez.Agent1 interface
        # Capability: "NoInputNoOutput" for headphones
        # Or "DisplayYesNo" if OLED can show confirmation
        pass

    async def discover(self, timeout=30):
        """Start discovery, yield found devices."""
        await self.adapter.call_start_discovery()
        # Monitor ObjectManager for new Device1 objects
        # Filter by audio-related UUIDs (A2DP sink: 0x110B)
        # Yield device info for UI
        await asyncio.sleep(timeout)
        await self.adapter.call_stop_discovery()

    async def pair_and_connect(self, mac: str):
        """Pair, trust, and connect to a device."""
        device_path = f"/org/bluez/hci0/dev_{mac.replace(':', '_')}"
        introspect = await self.bus.introspect("org.bluez", device_path)
        obj = self.bus.get_proxy_object("org.bluez", device_path, introspect)
        device = obj.get_interface("org.bluez.Device1")

        await device.call_pair()
        await device.set_trusted(True)
        await device.call_connect()

    async def _reconnect_trusted(self):
        """On startup, try to reconnect all trusted audio devices."""
        # Enumerate /org/bluez/hci0/dev_* objects
        # For each trusted device with A2DP UUID, attempt connect
        # Use exponential backoff on failure
        pass

    def _on_dbus_signal(self, msg):
        """Handle PropertiesChanged signals for connect/disconnect."""
        # Watch for Device1.Connected = True/False
        # Watch for MediaTransport1.State changes
        # On disconnect: start reconnect task
        # On connect: cancel reconnect, notify UI
        pass
```

### Auto-Reconnect: AirPods Case Behavior

**What happens when AirPods go in/out of case:**

1. **Put in case, lid open:** AirPods disconnect after ~30 seconds
2. **Close lid:** AirPods disconnect immediately
3. **Open lid:** AirPods enter pairing/connectable mode for ~60 seconds
4. **Remove from case:** AirPods are immediately connectable

**BlueZ reconnection behavior:**
- If device is **trusted** (`bluetoothctl trust <mac>`), BlueZ will auto-accept incoming connections
- AirPods initiate reconnection to the last connected device when removed from case
- If the Pi is the last connected device, AirPods should reconnect automatically
- **Problem:** AirPods prefer reconnecting to Apple devices. If an iPhone is nearby, they may connect there instead.

**Reconnection strategy:**

```python
async def _reconnect_loop(self, mac: str):
    """Persistent reconnect with exponential backoff."""
    backoff = self.RECONNECT_INTERVAL
    while True:
        try:
            await self.pair_and_connect(mac)
            return  # success
        except Exception:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, self.RECONNECT_MAX_BACKOFF)
```

**AirPods-specific fix:** After AirPods reconnect, the AAC codec may produce silence (known BlueZ/PipeWire bug, fixed in PipeWire 1.4+). Ensure PipeWire is up to date, or force SBC-XQ as fallback codec.

### PipeWire vs PulseAudio for A2DP on Pi Zero 2W

**Winner: PipeWire**

| Aspect | PulseAudio | PipeWire |
|--------|-----------|----------|
| A2DP codec support | SBC only (without modules) | SBC, SBC-XQ, AAC, LDAC, aptX out of box |
| Bluetooth reconnect | Manual intervention often needed | Automatic via WirePlumber |
| Audio quality on Pi Zero 2W | Choppy, stuttering reported | Minor hiccup every 30-60s |
| CPU usage | Higher | Lower |
| Default on RPi OS Bookworm+ | No | **Yes** (since Oct 2023) |
| AVRCP dummy player | Manual config | `bluez5.dummy-avrcp-player = true` in WirePlumber |
| Latency | Higher | Lower |

**PipeWire setup for A2DP:**

PipeWire is already default on Raspberry Pi OS Bookworm. For AVRCP support:

```bash
# /home/pi/.config/wireplumber/wireplumber.conf.d/51-bluez-avrcp.conf
monitor.bluez.properties = {
    bluez5.dummy-avrcp-player = true
}
```

**AVRCP dummy player** is needed so that AirPods can send media control commands. Without it, AirPods think there's no media player and some gestures don't work.

### D-Bus Signals for Connect/Disconnect Detection

```python
# Monitor device connection state changes
async def watch_connections(bus):
    """Watch for BT device connect/disconnect events."""

    def handler(msg):
        if msg.member == "PropertiesChanged":
            interface = msg.body[0]
            changed = msg.body[1]

            if interface == "org.bluez.Device1":
                if "Connected" in changed:
                    connected = changed["Connected"].value
                    device_path = msg.path
                    if connected:
                        print(f"Device connected: {device_path}")
                        # Trigger: update UI, start AAP client, route audio
                    else:
                        print(f"Device disconnected: {device_path}")
                        # Trigger: start reconnect, update UI

            if interface == "org.bluez.MediaTransport1":
                if "State" in changed:
                    state = changed["State"].value
                    # "idle" -> "pending" -> "active"
                    # "active" means audio is streaming

    bus.add_message_handler(handler)

    # Also add match rule for efficiency
    await bus.call(
        Message(
            destination="org.freedesktop.DBus",
            path="/org/freedesktop/DBus",
            interface="org.freedesktop.DBus",
            member="AddMatch",
            body=["type='signal',sender='org.bluez',interface='org.freedesktop.DBus.Properties',member='PropertiesChanged'"],
        )
    )
```

### BLE + Classic BT Coexistence on BCM43436s

The BCM43436s on Pi Zero 2W is a **dual-mode** chip that supports both Classic BT and BLE simultaneously. Key points:

- **It works.** The chip has a hardware coexistence controller that schedules Classic and BLE activities to minimize interference.
- **A2DP + BLE GATT server** can run simultaneously. The chip interleaves BLE advertisement/connection events in gaps between A2DP audio packets.
- **Performance impact:** A2DP streaming is bandwidth-intensive. During active audio streaming, BLE throughput may be reduced (higher latency, fewer connection events per second). This is fine for companion app GATT, which is low-bandwidth.
- **WiFi coexistence** is the bigger concern. A2DP + WiFi on the same 2.4GHz radio causes contention. Minimize WiFi traffic during audio streaming. Consider: WiFi for API calls, BT for audio, don't do large downloads during music playback.

**Practical architecture:**
```
BCM43436s
  |
  +-- Classic BT: A2DP sink (audio to headphones)
  |                AVRCP (media controls)
  |                HFP (voice calls, optional)
  |
  +-- BLE: GATT server (companion app pairing/control)
  |        BLE scan (optional, for device discovery)
  |
  +-- WiFi: API calls to server, OTA updates
```

### Power Consumption: Scanning Strategies

**Pi Zero 2W baseline:** ~120mA @ 5V idle (600mW)

| BT Activity | Additional Draw | Notes |
|------------|----------------|-------|
| BLE advertising | ~1-2mA | Negligible |
| BLE scanning (continuous) | ~5-10mA | Noticeable on battery |
| BLE connected (idle) | ~1-2mA | Negligible |
| Classic BT connected (idle) | ~2-3mA | Negligible |
| A2DP streaming | ~15-25mA | Significant during playback |
| Discovery scan (inquiry) | ~10-15mA | Only during wizard |

**Recommended strategy:**

1. **No continuous scanning.** Only scan during pairing wizard or when explicitly requested.
2. **Rely on incoming connections.** AirPods initiate reconnection when removed from case. BlueZ accepts if device is trusted.
3. **Periodic reconnect attempts.** If a trusted device is not connected, try `device.call_connect()` every 30-60 seconds rather than scanning. This is lower power than discovery scanning.
4. **Disable discovery when not in wizard.** `adapter.set_discoverable(False)` and don't call `start_discovery()` outside the pairing flow.

### Pairing Wizard UI Flow (240x280 OLED, Single Button)

The wizard should use the BITOS navigation convention (assuming single button with tap/double-tap/long-press).

```
Screen 1: "Bluetooth Setup"
  > Scan for devices
    Paired devices (N)
    Back

  [TAP to select, LONG to go back]

Screen 2: "Scanning..." (animated)
  Found devices appear as list:
    AirPods Pro (Seb)    -42dBm
    JBL Flip 6           -65dBm
    ...

  [TAP to select device, LONG to cancel]

Screen 3: "Pairing..."
  Connecting to:
  AirPods Pro (Seb)
  [spinning indicator]

  Success -> Screen 4
  Fail -> "Pairing failed. Retry?" [TAP=yes, LONG=back]

Screen 4: "Connected!"
  AirPods Pro (Seb)
  Battery: L:85% R:90% C:100%
  Audio: A2DP (AAC)

  > Set as default
    Forget device
    Back

Screen 5: "Paired Devices"
  AirPods Pro (Seb)  [connected]
  JBL Flip 6         [disconnected]

  [TAP to select, shows device detail]
  [LONG to go back]
```

**Implementation pattern:**

```python
class PairingWizard:
    """Drives the OLED pairing wizard flow."""

    def __init__(self, bt_manager, display):
        self.bt = bt_manager
        self.display = display
        self.state = "menu"
        self.found_devices = []
        self.selected_index = 0

    async def on_button(self, event: str):
        """Handle button events: 'tap', 'double', 'long'."""
        if self.state == "menu":
            if event == "tap":
                await self._next_item()
            elif event == "double":
                await self._select_item()
            elif event == "long":
                await self._go_back()

        elif self.state == "scanning":
            if event == "tap":
                await self._next_item()
            elif event == "double":
                device = self.found_devices[self.selected_index]
                await self._start_pairing(device)
            elif event == "long":
                await self.bt.stop_discovery()
                self.state = "menu"

    async def _start_scanning(self):
        self.state = "scanning"
        self.found_devices = []
        self.display.show_scanning()

        async for device in self.bt.discover():
            if self._is_audio_device(device):
                self.found_devices.append(device)
                self.display.update_device_list(self.found_devices)

    def _is_audio_device(self, device):
        """Filter for A2DP devices by UUID."""
        A2DP_SINK = "0000110b-0000-1000-8000-00805f9b34fb"
        HANDSFREE = "0000111e-0000-1000-8000-00805f9b34fb"
        return A2DP_SINK in device.uuids or HANDSFREE in device.uuids
```

### Recommended Architecture: Unified BT Service

```python
# bt_service.py — single async service managing all BT

class BTService:
    """Unified Bluetooth service for BITOS."""

    def __init__(self):
        self.connection_manager = BTConnectionManager()
        self.aap_client = AAPClient()          # AAP protocol (Part 1)
        self.pairing_wizard = PairingWizard()
        self.event_bus = asyncio.Queue()        # events to UI/app

    async def start(self):
        await self.connection_manager.start()

        # When audio device connects, start AAP if it's AirPods
        self.connection_manager.on_connect = self._on_device_connect
        self.connection_manager.on_disconnect = self._on_device_disconnect

    async def _on_device_connect(self, mac: str, device_info: dict):
        """Called when a BT device connects."""
        await self.event_bus.put(("bt_connected", mac, device_info))

        # If AirPods, start AAP client for gesture detection
        if self._is_airpods(device_info):
            await self.aap_client.connect(mac)
            self.aap_client.on_stem_press = self._on_stem_press
            self.aap_client.on_ear_detect = self._on_ear_detect
            self.aap_client.on_battery = self._on_battery

    async def _on_device_disconnect(self, mac: str):
        """Called when a BT device disconnects."""
        await self.event_bus.put(("bt_disconnected", mac))
        if self.aap_client.connected_mac == mac:
            self.aap_client.disconnect()
        # Connection manager auto-starts reconnect

    async def _on_stem_press(self, press_type: str):
        """Handle AirPods stem press via AAP."""
        # press_type: "single", "double", "triple", "long"
        await self.event_bus.put(("gesture", press_type))

    async def _on_ear_detect(self, left_in: bool, right_in: bool):
        """Handle ear detection state change."""
        if not left_in and not right_in:
            await self.event_bus.put(("audio", "pause"))
        else:
            await self.event_bus.put(("audio", "resume"))

    async def _on_battery(self, left: int, right: int, case: int):
        """Handle battery update."""
        await self.event_bus.put(("battery", {"L": left, "R": right, "C": case}))

    def _is_airpods(self, device_info: dict) -> bool:
        """Detect AirPods by manufacturer data or name."""
        name = device_info.get("Name", "")
        return "airpods" in name.lower()
```

### Key Implementation Notes

1. **bluetoothctl as test harness.** Before writing Python code, test the full flow manually:
   ```bash
   bluetoothctl
   > power on
   > agent NoInputNoOutput
   > default-agent
   > scan on
   # Wait for AirPods to appear
   > pair XX:XX:XX:XX:XX:XX
   > trust XX:XX:XX:XX:XX:XX
   > connect XX:XX:XX:XX:XX:XX
   ```

2. **AirPods pairing quirk.** AirPods must be in the case with lid open and the button on the back held until the LED flashes white. Only then will they appear in discovery.

3. **Profile auto-connect order.** After pairing, BlueZ automatically connects A2DP and AVRCP profiles. HFP may also connect. The AAP L2CAP connection (PSM 0x1001) must be established separately by our code — BlueZ doesn't know about this proprietary channel.

4. **Thread safety.** All BlueZ D-Bus calls and the AAP socket should run on the same asyncio event loop. Use `asyncio.get_event_loop().add_reader()` for the raw L2CAP socket.

5. **Graceful degradation.** If AAP connection fails (e.g., non-AirPods headphones), fall back to AVRCP-only mode. The BT manager should work with any A2DP device, not just AirPods.

---

## Summary: Recommended Implementation Roadmap

### Phase 1: Basic BT Manager (1-2 days)
- `dbus-next` based connection manager
- Scan, pair, trust, connect via D-Bus
- Auto-reconnect on disconnect with exponential backoff
- D-Bus signal monitoring for connect/disconnect events
- PipeWire A2DP routing (should work automatically)

### Phase 2: Pairing Wizard UI (1 day)
- OLED wizard flow (scan -> select -> pair -> confirm)
- Device list with signal strength
- Paired device management screen
- Integration with existing BITOS menu system

### Phase 3: AAP Client for AirPods (2-3 days)
- L2CAP socket connection to PSM 0x1001
- AAP handshake implementation
- Notification subscription
- Stem press event parsing (single/double/triple/long)
- Battery, ear detection, noise control parsing
- Event dispatch to BITOS action system

### Phase 4: Polish (1 day)
- AirPods-specific reconnection handling (case open/close)
- AAC codec reconnection bug workaround
- Battery status display in BITOS status bar
- Noise control toggle from BITOS UI

### Optional: BNO085 IMU Integration (1 day)
- I2C connection, rotation vector streaming
- Nod/shake detection algorithm
- Map to BITOS yes/no gestures

---

## Sources

### LibrePods / AAP Protocol
- [LibrePods GitHub](https://github.com/kavishdevar/librepods)
- [LibrePods Linux README](https://github.com/kavishdevar/librepods/blob/main/linux/README.md)
- [LibrePods AAP Definitions](https://github.com/kavishdevar/librepods/blob/main/AAP%20Definitions.md)
- [LibrePods Feature Reference (DeepWiki)](https://deepwiki.com/kavishdevar/librepods/6-feature-reference)
- [AAP Protocol Definition (tyalie)](https://github.com/tyalie/AAP-Protocol-Defintion)
- [LibrePods on Linux (Linuxiac)](https://linuxiac.com/airpods-on-linux-librepods-project-makes-it-possible/)
- [LibrePods on Linux (OMG Ubuntu)](https://www.omgubuntu.co.uk/2025/11/airpods-linux-librepods-anc-transparency-mode)

### AirPods / AVRCP on Linux
- [AirPods Pro 2 tap issue (Arch Forums)](https://bbs.archlinux.org/viewtopic.php?id=296994)
- [BlueZ AVRCP Implementation (DeepWiki)](https://deepwiki.com/bluez/bluez/4.3-avrcp)
- [AAC Codec Reconnect Bug (BlueZ #1093)](https://github.com/bluez/bluez/issues/1093)
- [A2DP Reconnect Issue (BlueZ #128)](https://github.com/bluez/bluez/issues/128)
- [Evsieve Input Remapper](https://github.com/KarsMulder/evsieve)

### BNO085 IMU
- [Adafruit BNO085 Overview](https://learn.adafruit.com/adafruit-9-dof-orientation-imu-fusion-breakout-bno085?view=all)
- [BNO085 Report Types](https://learn.adafruit.com/adafruit-9-dof-orientation-imu-fusion-breakout-bno085/report-types)
- [BNO085 UART-RVC Mode](https://learn.adafruit.com/adafruit-9-dof-orientation-imu-fusion-breakout-bno085/uart-rvc-for-python-circuitpython)

### Bluetooth Management / PipeWire
- [Python BlueZ D-Bus (ukBaz)](https://ukbaz.github.io/howto/python_gio_1.html)
- [Bluezero Library](https://github.com/ukBaz/python-bluezero)
- [Pi as BT Speaker with PipeWire (Collabora)](https://www.collabora.com/news-and-blog/blog/2022/09/02/using-a-raspberry-pi-as-a-bluetooth-speaker-with-pipewire-wireplumber/)
- [PipeWire + BT on Pi Zero 2W (RPi Forums)](https://forums.raspberrypi.com/viewtopic.php?t=392624)
- [Headless A2DP Streaming Guide](https://gist.github.com/mill1000/74c7473ee3b4a5b13f6325e9994ff84c)
- [Dual-Mode BT Coexistence (Ezurio)](https://www.ezurio.com/resources/blog/dual-mode-bluetooth-classic-ble-coexistence)
- [Pi Zero 2W Power Consumption (CNX Software)](https://www.cnx-software.com/2021/12/09/raspberry-pi-zero-2-w-power-consumption/)
- [BT Auto-Connect Fix (TechWiser)](https://techwiser.com/fix-bluetooth-device-doesnt-auto-connect-in-linux/)
- [org.bluez.Device1 Man Page](https://man.archlinux.org/man/extra/bluez-utils/org.bluez.Device.5.en)
