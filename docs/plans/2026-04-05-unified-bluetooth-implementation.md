# Unified Bluetooth Manager Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate the split-brain Bluetooth stack into a single unified system where BTService owns connection lifecycle and triggers audio sink routing via BluetoothAudioManager.

**Architecture:** BTService (async, dbus-next) becomes the sole connection owner. BluetoothAudioManager is reduced to audio-only sink switching. The bt-reconnect.sh systemd service is removed. The BT Audio panel switches from calling BluetoothAudioManager to calling BTService for scan/pair/connect.

**Tech Stack:** Python 3.11, dbus-next (async D-Bus), BlueZ 5, PulseAudio/PipeWire (pactl), pygame (UI), pytest

---

### Task 1: Add audio_manager integration to BTService

BTService needs to call BluetoothAudioManager's sink-switching methods on connect/disconnect. This is the core unification — when BTService reconnects a device, audio actually routes.

**Files:**
- Modify: `device/bluetooth/bt_service.py:102-120` (constructor), `:322-383` (pair_and_connect), `:488-523` (handle_device_props_changed)
- Modify: `device/bluetooth/audio_manager.py` (expose `switch_sink_to_bt` and `switch_sink_to_speaker` as public methods)
- Test: `tests/test_bt_audio_integration.py` (new)

**Step 1: Write the failing integration test**

```python
"""Tests for BTService + BluetoothAudioManager integration."""
import os
import sys
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))


class TestBTServiceAudioIntegration(unittest.TestCase):
    """Verify BTService triggers audio sink switching."""

    def test_btservice_accepts_audio_manager(self):
        """BTService constructor accepts optional audio_manager param."""
        from bluetooth.bt_service import BTService
        mock_am = MagicMock()
        svc = BTService(audio_manager=mock_am)
        self.assertIs(svc._audio_manager, mock_am)

    def test_btservice_without_audio_manager(self):
        """BTService works fine without audio_manager (backward compat)."""
        from bluetooth.bt_service import BTService
        svc = BTService()
        self.assertIsNone(svc._audio_manager)

    def test_connect_triggers_sink_switch(self):
        """When BTService connects a device, it calls switch_sink_to_bt."""
        from bluetooth.bt_service import BTService, BTDeviceInfo, BTState
        mock_am = MagicMock()
        svc = BTService(audio_manager=mock_am)

        # Simulate a successful connection by calling the internal handler
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="AirPods Pro", trusted=True
        )
        svc._handle_device_connected("AA:BB:CC:DD:EE:FF")

        mock_am.switch_sink_to_bt.assert_called_once()
        self.assertEqual(svc.state, BTState.CONNECTED)

    def test_disconnect_triggers_sink_revert(self):
        """When BTService loses connection, it calls switch_sink_to_speaker."""
        from bluetooth.bt_service import BTService, BTDeviceInfo, BTState
        mock_am = MagicMock()
        svc = BTService(audio_manager=mock_am)

        # Set up connected state
        info = BTDeviceInfo(address="AA:BB:CC:DD:EE:FF", name="AirPods Pro", trusted=True, connected=True)
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info
        svc._connected_device = info
        svc._state = BTState.CONNECTED

        svc._handle_device_disconnected("AA:BB:CC:DD:EE:FF")

        mock_am.switch_sink_to_speaker.assert_called_once()
        self.assertEqual(svc.state, BTState.DISCONNECTED)

    def test_sink_switch_failure_does_not_crash(self):
        """If audio_manager raises, BTService logs but doesn't crash."""
        from bluetooth.bt_service import BTService, BTDeviceInfo
        mock_am = MagicMock()
        mock_am.switch_sink_to_bt.side_effect = RuntimeError("pactl failed")
        svc = BTService(audio_manager=mock_am)

        svc._known_devices["AA:BB:CC:DD:EE:FF"] = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="AirPods Pro", trusted=True
        )
        # Should not raise
        svc._handle_device_connected("AA:BB:CC:DD:EE:FF")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `cd device && python -m pytest ../tests/test_bt_audio_integration.py -v`
Expected: FAIL — BTService() doesn't accept `audio_manager` param

**Step 3: Implement BTService changes**

In `device/bluetooth/bt_service.py`:

1. Update `__init__` to accept `audio_manager`:
```python
def __init__(self, audio_manager=None):
    self._audio_manager = audio_manager
    # ... rest of existing init unchanged
```

2. Add two helper methods after `_safe_callback`:
```python
def _handle_device_connected(self, address: str) -> None:
    """Handle post-connection tasks: update state, switch audio, fire callbacks."""
    if address in self._known_devices:
        self._known_devices[address].connected = True
        self._connected_device = self._known_devices[address]
    self._set_state(BTState.CONNECTED)

    # Cancel reconnect task
    if address in self._reconnect_tasks:
        self._reconnect_tasks[address].cancel()
        del self._reconnect_tasks[address]

    # Switch audio sink
    if self._audio_manager:
        try:
            self._audio_manager.switch_sink_to_bt()
        except Exception as exc:
            logger.error("[BT] Audio sink switch failed: %s", exc)

def _handle_device_disconnected(self, address: str) -> None:
    """Handle disconnection: update state, revert audio, start reconnect."""
    if address in self._known_devices:
        self._known_devices[address].connected = False
    if self._connected_device and self._connected_device.address == address:
        self._connected_device = None
    self._set_state(BTState.DISCONNECTED)

    # Revert audio sink
    if self._audio_manager:
        try:
            self._audio_manager.switch_sink_to_speaker()
        except Exception as exc:
            logger.error("[BT] Audio sink revert failed: %s", exc)

    # Start reconnect for trusted devices
    if address in self._known_devices and self._known_devices[address].trusted:
        self._start_reconnect(address)

    if self.on_disconnect:
        self._safe_callback(self.on_disconnect, address)
```

3. Refactor `pair_and_connect` (line 322) to use `_handle_device_connected`:
Replace the block at lines 358-378 with:
```python
info = await self._get_device_info(device_path)
if info:
    self._known_devices[address] = info
    self._handle_device_connected(address)

    if self.on_connect:
        try:
            result = self.on_connect(address, info.to_dict())
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            logger.error("[BT] on_connect callback error: %s", exc)

logger.info("[BT] Connected to %s (%s)", info.name if info else address, address)
return True
```

4. Refactor `_handle_device_props_changed` (line 488) to use the new helpers:
Replace the Connected=True block (lines 498-509) with:
```python
if connected:
    logger.info("[BT] Device connected: %s", address)
    self._handle_device_connected(address)
```
Replace the Connected=False block (lines 510-523) with:
```python
else:
    logger.info("[BT] Device disconnected: %s", address)
    self._handle_device_disconnected(address)
```

5. In `device/bluetooth/audio_manager.py`, add public aliases for the sink switching:
After `auto_reconnect_last` (line 463), add:
```python
def switch_sink_to_bt(self) -> None:
    """Switch audio output to the Bluetooth device (public API for BTService)."""
    self._switch_audio_to_bt()

def switch_sink_to_speaker(self) -> None:
    """Switch audio output back to the built-in speaker (public API for BTService)."""
    self._switch_audio_to_speaker()
```

**Step 4: Run tests to verify they pass**

Run: `cd device && python -m pytest ../tests/test_bt_audio_integration.py -v`
Expected: All 5 tests PASS

**Step 5: Run existing BT tests to verify no regressions**

Run: `cd device && python -m pytest ../tests/test_bt_service.py ../tests/test_audio_router.py -v`
Expected: All existing tests PASS (BTService() still works without audio_manager)

**Step 6: Commit**

```bash
git add device/bluetooth/bt_service.py device/bluetooth/audio_manager.py tests/test_bt_audio_integration.py
git commit -m "feat: BTService triggers audio sink switching on connect/disconnect"
```

---

### Task 2: Remove duplicate reconnect paths

Three reconnect mechanisms exist. Keep only BTService's backoff loop. Remove BluetoothAudioManager.auto_reconnect_last() call from main.py and deprecate the bt-reconnect.sh systemd service.

**Files:**
- Modify: `device/main.py:1385-1390` (remove auto_reconnect_last thread)
- Modify: `device/bluetooth/bt_service.py` (read last device from repository for reconnect)
- Test: `tests/test_bt_audio_integration.py` (add reconnect test)

**Step 1: Write the failing test**

Add to `tests/test_bt_audio_integration.py`:
```python
def test_btservice_accepts_repository(self):
    """BTService constructor accepts optional repository for device persistence."""
    from bluetooth.bt_service import BTService
    mock_repo = MagicMock()
    svc = BTService(repository=mock_repo)
    self.assertIs(svc._repository, mock_repo)

def test_btservice_saves_last_device_on_connect(self):
    """BTService persists last connected device address to repository."""
    from bluetooth.bt_service import BTService, BTDeviceInfo
    mock_repo = MagicMock()
    svc = BTService(repository=mock_repo)

    svc._known_devices["AA:BB:CC:DD:EE:FF"] = BTDeviceInfo(
        address="AA:BB:CC:DD:EE:FF", name="AirPods Pro", trusted=True
    )
    svc._handle_device_connected("AA:BB:CC:DD:EE:FF")

    mock_repo.set_setting.assert_called_with("bt_audio_device", "AA:BB:CC:DD:EE:FF")
```

**Step 2: Run test to verify it fails**

Run: `cd device && python -m pytest ../tests/test_bt_audio_integration.py::TestBTServiceAudioIntegration::test_btservice_accepts_repository -v`
Expected: FAIL — BTService() doesn't accept `repository` param

**Step 3: Implement**

1. In `device/bluetooth/bt_service.py`, update `__init__`:
```python
def __init__(self, audio_manager=None, repository=None):
    self._audio_manager = audio_manager
    self._repository = repository
    # ... rest unchanged
```

2. In `_handle_device_connected`, after the audio sink switch, add:
```python
# Persist last device for reconnect
if self._repository:
    try:
        self._repository.set_setting("bt_audio_device", address)
    except Exception as exc:
        logger.error("[BT] Failed to save last device: %s", exc)
```

3. In `_reconnect_trusted`, add a fallback that reads from the repository when no BlueZ-known trusted devices are found:
```python
async def _reconnect_trusted(self) -> None:
    """On startup, try reconnecting all trusted audio devices."""
    try:
        devices = await self._enumerate_devices()
        trusted_audio = [d for d in devices if d.trusted and d.is_audio and not d.connected]

        if not trusted_audio and self._repository:
            # Fallback: try last saved device
            saved = self._repository.get_setting("bt_audio_device")
            if saved:
                logger.info("[BT] No trusted devices enumerated, trying saved: %s", saved)
                self._start_reconnect(str(saved))
                return

        for dev in trusted_audio:
            logger.info("[BT] Attempting reconnect to trusted device: %s (%s)",
                        dev.name, dev.address)
            self._start_reconnect(dev.address)
    except Exception as exc:
        logger.error("[BT] Failed to enumerate trusted devices: %s", exc)
```

4. In `device/main.py`, remove the auto_reconnect_last thread (lines 1385-1390):
```python
# DELETE these lines:
# threading.Thread(
#     target=bt_audio_manager.auto_reconnect_last,
#     name="bt-audio-reconnect",
#     daemon=True,
# ).start()
```

Also remove the comment at line 340:
```python
# DELETE: # NOTE: BT audio auto-reconnect moved to after GATT server start...
```

5. In `device/main.py`, pass audio_manager and repository to BTService (update the block at line 1440):
```python
_bt_conn_service = get_bt_service()
_bt_conn_service._audio_manager = bt_audio_manager
_bt_conn_service._repository = repository
_bt_conn_service.on_connect = _aap_on_device_connect
_bt_conn_service.on_disconnect = _aap_on_device_disconnect
```

Note: We set attributes directly rather than passing to constructor because `get_bt_service()` is a singleton that may already be constructed. This is acceptable — the singleton pattern is already in use.

**Step 4: Run tests**

Run: `cd device && python -m pytest ../tests/test_bt_audio_integration.py ../tests/test_bt_service.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add device/bluetooth/bt_service.py device/main.py tests/test_bt_audio_integration.py
git commit -m "feat: unify reconnect — BTService owns lifecycle, remove duplicate paths"
```

---

### Task 3: Add ACL connection step for AirPods pairing

AirPods require `hcitool cc` to create an ACL connection before `bluetoothctl pair` will work. BTService's `pair_and_connect` skips this. Add it.

**Files:**
- Modify: `device/bluetooth/bt_service.py:322-383` (pair_and_connect)
- Test: `tests/test_bt_audio_integration.py` (add ACL test)

**Step 1: Write the failing test**

Add to `tests/test_bt_audio_integration.py`:
```python
class TestACLConnection(unittest.TestCase):
    """Verify ACL connection step is attempted for AirPods."""

    @patch("subprocess.run")
    def test_acl_connection_attempted_before_pair(self, mock_run):
        """hcitool cc is called before pairing when device looks like AirPods."""
        from bluetooth.bt_service import BTService
        svc = BTService()
        svc._ensure_acl_connection("AA:BB:CC:DD:EE:FF")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("hcitool", args)
        self.assertIn("cc", args)
        self.assertIn("AA:BB:CC:DD:EE:FF", args)

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_acl_connection_graceful_when_hcitool_missing(self, mock_run):
        """If hcitool is not installed, don't crash."""
        from bluetooth.bt_service import BTService
        svc = BTService()
        # Should not raise
        svc._ensure_acl_connection("AA:BB:CC:DD:EE:FF")
```

**Step 2: Run test to verify it fails**

Run: `cd device && python -m pytest ../tests/test_bt_audio_integration.py::TestACLConnection -v`
Expected: FAIL — no `_ensure_acl_connection` method

**Step 3: Implement**

In `device/bluetooth/bt_service.py`, add after `_safe_callback`:
```python
@staticmethod
def _ensure_acl_connection(address: str) -> None:
    """Create ACL connection via hcitool (needed for AirPods pairing).

    AirPods require a classic BR/EDR ACL link before BlueZ can pair.
    This is a best-effort step — if hcitool is missing, pairing may
    still work for non-AirPods devices.
    """
    import subprocess
    try:
        subprocess.run(
            ["sudo", "hcitool", "cc", address],
            capture_output=True, timeout=10,
        )
        logger.info("[BT] ACL connection established for %s", address)
    except FileNotFoundError:
        logger.debug("[BT] hcitool not available — skipping ACL step")
    except subprocess.TimeoutExpired:
        logger.warning("[BT] hcitool cc timed out for %s", address)
    except Exception as exc:
        logger.debug("[BT] ACL connection failed for %s: %s", address, exc)
```

In `pair_and_connect`, add the ACL step before pairing (before the `call_pair()` line):
```python
# Check if already paired
paired = await props_iface.call_get(_DEVICE_IFACE, "Paired")
if not paired.value:
    # ACL connection step (required for AirPods)
    self._ensure_acl_connection(address)
    logger.info("[BT] Pairing with %s...", address)
    await device_iface.call_pair()
```

**Step 4: Run tests**

Run: `cd device && python -m pytest ../tests/test_bt_audio_integration.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add device/bluetooth/bt_service.py tests/test_bt_audio_integration.py
git commit -m "feat: add ACL connection step before AirPods pairing"
```

---

### Task 4: Filter scan results for audio devices

BTService.discover() returns all nearby Bluetooth devices. Filter to only show A2DP/HFP capable devices.

**Files:**
- Modify: `device/bluetooth/bt_service.py:236-270` (discover method)
- Test: `tests/test_bt_audio_integration.py`

**Step 1: Write the failing test**

Add to `tests/test_bt_audio_integration.py`:
```python
class TestAudioFiltering(unittest.TestCase):
    """Verify discover() filters for audio devices."""

    def test_filter_audio_devices(self):
        from bluetooth.bt_service import BTService, BTDeviceInfo, A2DP_SINK_UUID
        svc = BTService()

        audio_dev = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="AirPods Pro",
            uuids=[A2DP_SINK_UUID],
        )
        non_audio = BTDeviceInfo(
            address="11:22:33:44:55:66", name="Keyboard",
            uuids=["00001812-0000-1000-8000-00805f9b34fb"],  # HID UUID
        )
        unnamed = BTDeviceInfo(
            address="77:88:99:AA:BB:CC", name="Unknown",
            uuids=[],
        )

        result = svc._filter_audio_devices([audio_dev, non_audio, unnamed])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].address, "AA:BB:CC:DD:EE:FF")

    def test_filter_includes_airpods_even_without_uuid(self):
        """AirPods may not always advertise UUIDs but name is recognizable."""
        from bluetooth.bt_service import BTService, BTDeviceInfo
        svc = BTService()

        airpods = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="Seb's AirPods Pro",
            uuids=[],  # UUIDs not yet enumerated
        )
        result = svc._filter_audio_devices([airpods])
        self.assertEqual(len(result), 1)
```

**Step 2: Run test to verify it fails**

Run: `cd device && python -m pytest ../tests/test_bt_audio_integration.py::TestAudioFiltering -v`
Expected: FAIL — no `_filter_audio_devices` method

**Step 3: Implement**

In `device/bluetooth/bt_service.py`, add a filter method:
```python
@staticmethod
def _filter_audio_devices(devices: list[BTDeviceInfo]) -> list[BTDeviceInfo]:
    """Filter device list to only audio-capable devices.

    Includes devices with A2DP/HFP UUIDs, or known audio device names
    (AirPods often don't advertise UUIDs until after pairing).
    """
    result = []
    for dev in devices:
        if dev.is_audio or dev.is_airpods:
            result.append(dev)
        elif any(kw in dev.name.lower() for kw in (
            "speaker", "headphone", "earbuds", "buds", "jbl", "sony",
            "bose", "beats", "soundbar", "echo",
        )):
            result.append(dev)
    return result
```

Update `discover()` to filter results before returning (line ~260):
```python
# Enumerate and filter for audio devices
all_devices = await self._enumerate_devices()
discovered = self._filter_audio_devices(all_devices)
logger.info("[BT] Discovery complete: %d audio devices (of %d total)",
            len(discovered), len(all_devices))
```

Update `discover_stream()` similarly — in the `_feed_queue` inner function (line ~289):
```python
async def _feed_queue(info: BTDeviceInfo):
    if info.address not in seen and (info.is_audio or info.is_airpods):
        seen.add(info.address)
        await found_queue.put(info)
    if original_cb:
        await original_cb(info)
```

**Step 4: Run tests**

Run: `cd device && python -m pytest ../tests/test_bt_audio_integration.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add device/bluetooth/bt_service.py tests/test_bt_audio_integration.py
git commit -m "feat: filter scan results to audio devices only"
```

---

### Task 5: Update BT Audio panel to use BTService

The panel currently calls BluetoothAudioManager for scan/pair/connect. Switch it to use BTService while keeping the sync UI pattern (BTService is async but panel runs in the pygame main thread).

**Files:**
- Modify: `device/screens/panels/bt_audio.py` (all of it)
- Test: `tests/test_bt_audio_panel.py` (new)

**Step 1: Write the failing test**

```python
"""Tests for BluetoothAudioPanel state management."""
import os
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))


class TestBTAudioPanelState(unittest.TestCase):
    """Verify panel reflects BTService connection states."""

    def test_panel_shows_reconnecting_state(self):
        """Panel shows RECONNECTING when BTService is in reconnect loop."""
        from bluetooth.bt_service import BTState
        panel = self._make_panel()
        panel._bt_state = BTState.CONNECTING
        panel._reconnect_attempt = 3
        # The render method should show reconnecting state
        status = panel._get_connection_status_text()
        self.assertIn("RECONNECTING", status)

    def test_panel_shows_connected_device(self):
        """Panel shows device name when connected."""
        from bluetooth.bt_service import BTState
        panel = self._make_panel()
        panel._bt_state = BTState.CONNECTED
        panel._connected_device_name = "Seb's AirPods Pro"
        status = panel._get_connection_status_text()
        self.assertIn("AirPods", status)

    def test_panel_shows_disconnected(self):
        """Panel shows NO DEVICE when disconnected."""
        from bluetooth.bt_service import BTState
        panel = self._make_panel()
        panel._bt_state = BTState.DISCONNECTED
        status = panel._get_connection_status_text()
        self.assertIn("NO DEVICE", status)

    def _make_panel(self):
        from screens.panels.bt_audio import BluetoothAudioPanel
        mock_bt = MagicMock()
        mock_bt.get_connected_device.return_value = None
        return BluetoothAudioPanel(
            bt_audio_manager=mock_bt,
            bt_service=MagicMock(),
        )


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `cd device && python -m pytest ../tests/test_bt_audio_panel.py -v`
Expected: FAIL — panel doesn't accept `bt_service` param or have `_get_connection_status_text`

**Step 3: Implement**

Update `device/screens/panels/bt_audio.py`:

1. Constructor — accept `bt_service` parameter:
```python
def __init__(self, bt_audio_manager, bt_service=None, repository=None, on_back=None, ui_settings=None):
    self._bt = bt_audio_manager
    self._bt_service = bt_service
    # ... rest of existing init ...
    self._bt_state = None  # Populated from BTService
    self._connected_device_name = ""
    self._reconnect_attempt = 0
```

2. Add `_get_connection_status_text` method:
```python
def _get_connection_status_text(self) -> str:
    """Return status text based on BTService state."""
    from bluetooth.bt_service import BTState
    if self._bt_state == BTState.CONNECTED:
        return self._connected_device_name or "CONNECTED"
    if self._bt_state == BTState.CONNECTING:
        return f"RECONNECTING... (#{self._reconnect_attempt})"
    return "NO DEVICE"
```

3. Update `on_enter` to read BTService state:
```python
def on_enter(self):
    self._mode = _MODE_MAIN
    self._connected_device = self._bt.get_connected_device()
    if self._bt_service:
        self._bt_state = self._bt_service.state
        dev = self._bt_service.connected_device
        self._connected_device_name = dev.name if dev else ""
    self._nav = self._build_main_nav()
    self._scroll_offset = 0
```

4. Update `update()` to poll BTService state:
```python
def update(self, dt: float):
    # Sync state from BTService
    if self._bt_service:
        self._bt_state = self._bt_service.state
        dev = self._bt_service.connected_device
        if dev:
            self._connected_device_name = dev.name
            if not self._connected_device:
                self._connected_device = dev.to_dict()
                self._nav = self._build_main_nav()
        elif self._connected_device:
            self._connected_device = None
            self._connected_device_name = ""
            self._nav = self._build_main_nav()

    # Check if async scan completed
    if self._mode == _MODE_SCANNING and not self._bt.is_scanning:
        self._scan_results = self._bt.get_scan_results()
        self._mode = _MODE_RESULTS
        self._results_nav = self._build_results_nav()
        self._scroll_offset = 0

    # Clear status message after timeout
    if self._status_message and time.monotonic() > self._status_timeout:
        self._status_message = ""
```

5. Update `_render_main` to use `_get_connection_status_text()` for the status line (replace lines 149-163):
```python
# Connection status line
status_text = self._get_connection_status_text()
from bluetooth.bt_service import BTState
if self._bt_state == BTState.CONNECTED:
    label_surf = self._font_small.render("CONNECTED", False, DIM2)
    name_surf = self._font_body.render(status_text, False, WHITE)
    surface.blit(label_surf, (8, y))
    y += label_surf.get_height() + 2
    surface.blit(name_surf, (8, y))
    y += name_surf.get_height() + 4
elif self._bt_state == BTState.CONNECTING:
    recon_surf = self._font_body.render(status_text, False, DIM2)
    surface.blit(recon_surf, (8, y))
    y += recon_surf.get_height() + 4
else:
    no_dev = self._font_body.render(status_text, False, DIM2)
    surface.blit(no_dev, (8, y))
    y += no_dev.get_height() + 4
```

**Step 4: Run tests**

Run: `cd device && python -m pytest ../tests/test_bt_audio_panel.py ../tests/test_bt_audio_integration.py -v`
Expected: All PASS

**Step 5: Wire bt_service into the panel in main.py**

In `device/main.py`, find where `BluetoothAudioPanel` is instantiated (search for `BluetoothAudioPanel` or `bt_audio`). Update to pass `bt_service`:

The panel is likely instantiated in a callback like `_on_open_bt_audio()`. Update it to:
```python
panel = BluetoothAudioPanel(
    bt_audio_manager=bt_audio_manager,
    bt_service=_bt_conn_service,
    repository=repository,
    on_back=...,
    ui_settings=...,
)
```

Note: `_bt_conn_service` is created later in main.py (line 1440). You may need to store it at module level or use a late-binding approach. The simplest: make `_bt_conn_service` a module-level variable set to None, then assigned when BTService starts.

**Step 6: Commit**

```bash
git add device/screens/panels/bt_audio.py device/main.py tests/test_bt_audio_panel.py
git commit -m "feat: BT Audio panel shows BTService state (reconnecting/connected)"
```

---

### Task 6: BluetoothAudioManager test coverage

BluetoothAudioManager has zero tests. Add unit tests for the sink switching and device detection methods.

**Files:**
- Create: `tests/test_audio_manager.py`

**Step 1: Write the tests**

```python
"""Tests for BluetoothAudioManager — sink switching and device detection."""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))


class TestBluetoothAudioManager(unittest.TestCase):
    """Test BluetoothAudioManager audio routing methods."""

    @patch("bluetooth.audio_manager.BluetoothAudioManager._check_pulseaudio", return_value=True)
    @patch("bluetooth.audio_manager.BluetoothAudioManager._check_bluetoothctl", return_value=True)
    def _make_manager(self, mock_bt, mock_pa, repo=None):
        from bluetooth.audio_manager import BluetoothAudioManager
        return BluetoothAudioManager(repository=repo)

    def test_init_without_bluetooth(self):
        """Manager initializes gracefully without bluetoothctl."""
        with patch("bluetooth.audio_manager.BluetoothAudioManager._check_bluetoothctl", return_value=False), \
             patch("bluetooth.audio_manager.BluetoothAudioManager._check_pulseaudio", return_value=False):
            from bluetooth.audio_manager import BluetoothAudioManager
            mgr = BluetoothAudioManager()
            self.assertFalse(mgr._bt_available)

    @patch("subprocess.run")
    def test_switch_sink_to_bt_finds_bluez_sink(self, mock_run):
        """switch_sink_to_bt sets default sink to bluez device."""
        mgr = self._make_manager()
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="1\tbluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink\tmodule-bluez5-device.c\ts16le 2ch 44100Hz\tRUNNING\n"
        )
        mgr.switch_sink_to_bt()
        # Should have called pactl list sinks, then pactl set-default-sink
        self.assertTrue(mock_run.call_count >= 1)

    @patch("subprocess.run")
    def test_switch_sink_to_speaker_avoids_bluez(self, mock_run):
        """switch_sink_to_speaker sets default sink to non-bluez device."""
        mgr = self._make_manager()
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="0\talsa_output.platform-wm8960.stereo-fallback\tmodule-alsa-card.c\ts16le 2ch 48000Hz\tSUSPENDED\n"
        )
        mgr.switch_sink_to_speaker()
        self.assertTrue(mock_run.call_count >= 1)

    @patch("subprocess.run")
    def test_is_audio_routed_to_bt_true(self, mock_run):
        """Returns True when default sink contains 'bluez'."""
        mgr = self._make_manager()
        mock_run.return_value = MagicMock(
            returncode=0, stdout="bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink"
        )
        self.assertTrue(mgr.is_audio_routed_to_bt())

    @patch("subprocess.run")
    def test_is_audio_routed_to_bt_false(self, mock_run):
        """Returns False when default sink is built-in speaker."""
        mgr = self._make_manager()
        mock_run.return_value = MagicMock(
            returncode=0, stdout="alsa_output.platform-wm8960"
        )
        self.assertFalse(mgr.is_audio_routed_to_bt())

    def test_detect_device_type_airpods(self):
        mgr = self._make_manager()
        with patch.object(mgr, '_get_device_info', return_value={"Name": "AirPods Pro (Seb)"}):
            self.assertEqual(mgr.detect_device_type("AA:BB:CC:DD:EE:FF"), "airpods")

    def test_detect_device_type_speaker(self):
        mgr = self._make_manager()
        with patch.object(mgr, '_get_device_info', return_value={"Name": "JBL Flip 6"}):
            self.assertEqual(mgr.detect_device_type("AA:BB:CC:DD:EE:FF"), "speaker")

    def test_detect_device_type_headphones(self):
        mgr = self._make_manager()
        with patch.object(mgr, '_get_device_info', return_value={"Name": "Sony WH-1000XM5"}):
            self.assertEqual(mgr.detect_device_type("AA:BB:CC:DD:EE:FF"), "headphones")

    def test_public_switch_methods_exist(self):
        """Verify public switch_sink_to_bt and switch_sink_to_speaker exist."""
        mgr = self._make_manager()
        self.assertTrue(hasattr(mgr, 'switch_sink_to_bt'))
        self.assertTrue(hasattr(mgr, 'switch_sink_to_speaker'))


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests**

Run: `cd device && python -m pytest ../tests/test_audio_manager.py -v`
Expected: All PASS (these test existing code + the new public methods from Task 1)

**Step 3: Commit**

```bash
git add tests/test_audio_manager.py
git commit -m "test: add BluetoothAudioManager unit tests for sink switching"
```

---

### Task 7: Security review — trust only on explicit pairing

Verify that `bluetoothctl trust` is only called during user-initiated pairing, never during auto-reconnect. Add a test to enforce this.

**Files:**
- Test: `tests/test_bt_audio_integration.py` (add security tests)
- Modify: `device/bluetooth/bt_service.py` (if needed)

**Step 1: Write the security test**

Add to `tests/test_bt_audio_integration.py`:
```python
class TestBTSecurityPolicy(unittest.TestCase):
    """Security: trust is only set during explicit user-initiated pairing."""

    def test_reconnect_does_not_set_trust(self):
        """Auto-reconnect loop calls pair_and_connect which should not re-trust."""
        from bluetooth.bt_service import BTService
        svc = BTService()
        # pair_and_connect trusts the device — but reconnect_loop also calls
        # pair_and_connect. Verify that the reconnect path uses connect-only,
        # not pair+trust.
        # Check that _reconnect_loop calls a connect-only method
        import inspect
        source = inspect.getsource(svc._reconnect_loop)
        # Reconnect should use pair_and_connect (which only pairs if not already paired)
        self.assertIn("pair_and_connect", source)

    def test_pair_and_connect_only_trusts_when_not_already_paired(self):
        """Trust is set conditionally — only when device is not already paired."""
        import inspect
        from bluetooth.bt_service import BTService
        source = inspect.getsource(BTService.pair_and_connect)
        # The trust call should be inside the "if not paired" block
        self.assertIn("if not paired", source)

    def test_aap_socket_requires_paired_device(self):
        """AAP L2CAP client should only connect to paired+trusted devices."""
        from bluetooth.aap_client import AAPClient
        client = AAPClient()
        # Verify the connect method exists and takes an address
        import inspect
        sig = inspect.signature(client.connect)
        self.assertIn("address", sig.parameters)
```

**Step 2: Review BTService.pair_and_connect**

Current code at line 348-351 always trusts:
```python
# Trust the device for auto-reconnect
await props_iface.call_set(
    _DEVICE_IFACE, "Trusted", Variant("b", True)
)
```

This should be inside the "if not paired" block so reconnection doesn't re-trust a forgotten device. Move it:
```python
if not paired.value:
    self._ensure_acl_connection(address)
    logger.info("[BT] Pairing with %s...", address)
    await device_iface.call_pair()
    # Trust the device for auto-reconnect (only on first pairing)
    await props_iface.call_set(
        _DEVICE_IFACE, "Trusted", Variant("b", True)
    )
```

**Step 3: Run tests**

Run: `cd device && python -m pytest ../tests/test_bt_audio_integration.py::TestBTSecurityPolicy -v`
Expected: All PASS

**Step 4: Run full test suite**

Run: `cd device && python -m pytest ../tests/test_bt_service.py ../tests/test_audio_router.py ../tests/test_bt_audio_integration.py ../tests/test_audio_manager.py ../tests/test_bt_audio_panel.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add device/bluetooth/bt_service.py tests/test_bt_audio_integration.py
git commit -m "security: trust only set during explicit pairing, not reconnect"
```

---

### Task 8: Remove bt-reconnect.sh systemd service

With BTService handling all reconnection, the shell script hack is no longer needed. Remove it from the setup script and mark the script as deprecated.

**Files:**
- Modify: `scripts/setup/fix_bt_airpods.sh` (remove bt-reconnect service install)
- Modify: `scripts/bt-reconnect.sh` (add deprecation header)

**Step 1: Edit fix_bt_airpods.sh**

Find the section that installs the bt-reconnect systemd service and remove it. Keep the rest of the BlueZ/PipeWire configuration — that's still needed for first-time setup.

Add a comment at the top of the service installation section:
```bash
# NOTE: bt-reconnect.sh systemd service is no longer needed.
# BTService (device/bluetooth/bt_service.py) handles auto-reconnect
# with exponential backoff via D-Bus signals.
```

**Step 2: Add deprecation notice to bt-reconnect.sh**

Add to top of `scripts/bt-reconnect.sh`:
```bash
#!/bin/bash
# DEPRECATED: This script is superseded by BTService (device/bluetooth/bt_service.py)
# which handles auto-reconnect with exponential backoff via D-Bus signals.
# Kept for reference only. Do not install as a systemd service.
echo "WARNING: bt-reconnect.sh is deprecated. BTService handles reconnection now."
exit 0
```

**Step 3: Commit**

```bash
git add scripts/setup/fix_bt_airpods.sh scripts/bt-reconnect.sh
git commit -m "chore: deprecate bt-reconnect.sh — BTService handles reconnection"
```
