# Unified Bluetooth Manager — Design

**Date:** 2026-04-05
**Status:** Approved
**Builds on:** Existing BluetoothAudioManager, BTService, AAP client, BT Audio panel

---

## Problem

The Bluetooth stack has a split-brain architecture. Three independent mechanisms manage AirPods connections:

1. **BluetoothAudioManager** (sync, bluetoothctl subprocess) — handles audio sink routing but has single-shot reconnect with no retry
2. **BTService** (async, dbus-next) — handles connection lifecycle with proper backoff but doesn't trigger audio sink switching
3. **bt-reconnect.sh** (systemd service) — shell script with hardcoded MAC that monitors D-Bus for reconnection

When BTService reconnects AirPods, audio doesn't route because BluetoothAudioManager isn't notified. The shell script compensates but is fragile and device-specific.

Additionally:
- AirPods pairing skips the `hcitool cc` ACL step documented in the working manual flow
- Scan results include non-audio devices
- No test coverage for BluetoothAudioManager
- No integration tests for the full connect-to-audio flow

---

## Design

### Architecture: BTService as Single Owner

BTService becomes the sole connection lifecycle manager. BluetoothAudioManager is reduced to a thin audio-routing helper.

```
BTService (dbus-next, async)
  ├── owns: discovery, pairing, connection, reconnect
  ├── calls: BluetoothAudioManager.switch_sink_to_bt(address)
  ├── calls: BluetoothAudioManager.switch_sink_to_speaker()
  ├── calls: AudioRouter.on_bt_connect(device_type)
  ├── calls: AAPClient.connect() (for AirPods)
  └── persists: last device to repository

BluetoothAudioManager (sync, subprocess)
  ├── owns: PulseAudio/PipeWire sink switching only
  ├── removed: scan, pair, connect, auto_reconnect_last
  └── removed: device persistence (BTService owns this)

bt-reconnect.sh
  └── REMOVED — BTService handles all reconnection
```

### Changes by File

**device/bluetooth/bt_service.py:**
- Add `audio_manager` parameter to constructor
- On successful connect: call `audio_manager.switch_sink_to_bt(address)`
- On disconnect: call `audio_manager.switch_sink_to_speaker()`
- Read last device from repository for reconnect (not hardcoded MAC)
- Filter discovery results by A2DP/HFP UUID
- Add `hcitool cc` ACL step before pairing (AirPods requirement)

**device/bluetooth/audio_manager.py:**
- Keep: `switch_sink_to_bt(address)`, `switch_sink_to_speaker()`, PulseAudio/ALSA routing
- Remove: `scan()`, `scan_async()`, `pair()`, `connect()`, `disconnect()`, `forget()`, `auto_reconnect_last()`
- These become thin wrappers or are deleted — BTService handles the lifecycle

**device/main.py:**
- Pass `BluetoothAudioManager` instance to `BTService` constructor
- Remove the separate `auto_reconnect_last()` thread (BTService handles this)
- BTService's `on_connect` callback handles both audio routing and AAP start

**device/screens/panels/bt_audio.py:**
- Use BTService for scan/pair/connect instead of BluetoothAudioManager
- Add "RECONNECTING..." state display when BTService is in backoff loop
- Show connection state from BTService (DISCONNECTED/CONNECTING/CONNECTED/PLAYING)

**scripts/bt-reconnect.sh + fix_bt_airpods.sh:**
- Remove bt-reconnect.sh systemd service installation
- Keep fix_bt_airpods.sh for one-time BlueZ/PipeWire setup only

### Auto-Connect Flow (after unification)

1. Device boots → main.py creates BTService with audio_manager
2. BTService.start() → powers on adapter, enumerates trusted devices
3. BTService._reconnect_trusted() → finds last AirPods, starts backoff loop
4. Connection succeeds → BTService calls audio_manager.switch_sink_to_bt()
5. BTService fires on_connect → AudioRouter updates routing, AAP starts
6. AirPods go to sleep (in case) → D-Bus signal fires disconnect
7. BTService._start_reconnect() → starts backoff loop again
8. AirPods wake (out of case) → reconnect succeeds → audio routes automatically

### Single-Button UX

No changes to the navigation flow (Home → Settings → BT Audio). The panel changes:
- Status line shows BTService state: "CONNECTED: Seb's AirPods" / "RECONNECTING... (attempt 3)" / "DISCONNECTED"
- Scan uses BTService.discover_stream() for real-time results (async generator)
- Pair/connect goes through BTService with proper ACL step
- Auto-connect toggle: setting to enable/disable reconnect loop

### Security Considerations

- Pairing uses BlueZ "just works" mode (no PIN for A2DP) — standard for audio devices
- L2CAP AAP socket (PSM 0x1001) only opened to paired+trusted devices
- BTService only reconnects to devices marked trusted in BlueZ
- BLE GATT server auth (HMAC challenge-response) is separate and unchanged
- Review: ensure bluetoothctl trust is only called during explicit user-initiated pairing, never automatically

### Testing Plan

- Unit tests for BluetoothAudioManager sink switching (mock pactl/aplay)
- Unit tests for BTService connection lifecycle (mock dbus-next)
- Integration test: BTService connect triggers audio_manager.switch_sink_to_bt()
- Integration test: BTService disconnect triggers switch_sink_to_speaker()
- Integration test: reconnect loop with simulated backoff
- Security test: verify trust is only set during explicit pairing
- UI test: BT Audio panel reflects BTService state changes

---

## Not in Scope

- HFP mic switching (AirPods mic input) — separate feature
- Spotify/AVRCP media key integration — separate feature
- Multi-device support (connect to >1 BT audio device)
- Companion PWA Bluetooth changes
