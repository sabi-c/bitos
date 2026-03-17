"""Tests for Bluetooth connection manager (BTService).

All BlueZ/D-Bus interactions are mocked since we can't test real BT in CI.
"""
import os
import sys
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))


class TestBTDeviceInfo(unittest.TestCase):
    """Tests for BTDeviceInfo dataclass."""

    def test_basic_properties(self):
        from bluetooth.bt_service import BTDeviceInfo, A2DP_SINK_UUID
        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF",
            name="Test Device",
            rssi=-42,
            paired=True,
            trusted=True,
            connected=False,
            uuids=[A2DP_SINK_UUID],
        )
        self.assertEqual(info.address, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(info.name, "Test Device")
        self.assertTrue(info.is_audio)
        self.assertFalse(info.is_airpods)
        self.assertFalse(info.connected)

    def test_is_airpods_detection(self):
        from bluetooth.bt_service import BTDeviceInfo
        info = BTDeviceInfo(address="AA:BB:CC:DD:EE:FF", name="AirPods Pro (Seb)")
        self.assertTrue(info.is_airpods)

        info2 = BTDeviceInfo(address="AA:BB:CC:DD:EE:FF", name="JBL Flip 6")
        self.assertFalse(info2.is_airpods)

    def test_dbus_path(self):
        from bluetooth.bt_service import BTDeviceInfo
        info = BTDeviceInfo(address="AA:BB:CC:DD:EE:FF")
        self.assertEqual(info.dbus_path, "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF")

    def test_to_dict(self):
        from bluetooth.bt_service import BTDeviceInfo
        info = BTDeviceInfo(address="AA:BB:CC:DD:EE:FF", name="Test", rssi=-50)
        d = info.to_dict()
        self.assertEqual(d["address"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(d["name"], "Test")
        self.assertEqual(d["rssi"], -50)
        self.assertIn("is_audio", d)
        self.assertIn("is_airpods", d)

    def test_is_audio_with_handsfree_uuid(self):
        from bluetooth.bt_service import BTDeviceInfo, HANDSFREE_UUID
        info = BTDeviceInfo(address="AA:BB:CC:DD:EE:FF", uuids=[HANDSFREE_UUID])
        self.assertTrue(info.is_audio)

    def test_is_audio_without_audio_uuids(self):
        from bluetooth.bt_service import BTDeviceInfo
        info = BTDeviceInfo(address="AA:BB:CC:DD:EE:FF", uuids=["0000180a-0000-1000-8000-00805f9b34fb"])
        self.assertFalse(info.is_audio)


class TestBTState(unittest.TestCase):
    """Tests for BTState enum."""

    def test_states(self):
        from bluetooth.bt_service import BTState
        self.assertEqual(BTState.DISCONNECTED.value, "disconnected")
        self.assertEqual(BTState.CONNECTING.value, "connecting")
        self.assertEqual(BTState.CONNECTED.value, "connected")
        self.assertEqual(BTState.PLAYING.value, "playing")


class TestBTServiceInit(unittest.TestCase):
    """Tests for BTService initialization and basic methods."""

    def test_initial_state(self):
        from bluetooth.bt_service import BTService, BTState
        svc = BTService()
        self.assertEqual(svc.state, BTState.DISCONNECTED)
        self.assertIsNone(svc.connected_device)
        self.assertEqual(svc.known_devices, {})
        self.assertFalse(svc.is_available)

    def test_singleton(self):
        import bluetooth.bt_service as mod
        # Reset singleton
        mod._instance = None
        s1 = mod.get_bt_service()
        s2 = mod.get_bt_service()
        self.assertIs(s1, s2)
        mod._instance = None  # clean up

    def test_state_change_callback(self):
        from bluetooth.bt_service import BTService, BTState
        svc = BTService()
        states_seen = []

        def on_change(old, new):
            states_seen.append((old, new))

        svc.on_state_change = on_change
        svc._set_state(BTState.CONNECTING)
        svc._set_state(BTState.CONNECTED)
        svc._set_state(BTState.CONNECTED)  # same state, no callback

        self.assertEqual(len(states_seen), 2)
        self.assertEqual(states_seen[0], (BTState.DISCONNECTED, BTState.CONNECTING))
        self.assertEqual(states_seen[1], (BTState.CONNECTING, BTState.CONNECTED))


class TestBTServiceWithMockedDBus(unittest.TestCase):
    """Tests for BTService with mocked D-Bus interactions."""

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    @patch("bluetooth.bt_service._DBUS_AVAILABLE", False)
    def test_start_without_dbus(self):
        from bluetooth.bt_service import BTService
        svc = BTService()
        result = self._run(svc.start())
        self.assertFalse(result)
        self.assertFalse(svc.is_available)

    @patch("bluetooth.bt_service._DBUS_AVAILABLE", False)
    def test_discover_without_dbus(self):
        from bluetooth.bt_service import BTService
        svc = BTService()
        devices = self._run(svc.discover(timeout=0.1))
        self.assertEqual(devices, [])

    @patch("bluetooth.bt_service._DBUS_AVAILABLE", False)
    def test_pair_without_dbus(self):
        from bluetooth.bt_service import BTService
        svc = BTService()
        result = self._run(svc.pair_and_connect("AA:BB:CC:DD:EE:FF"))
        self.assertFalse(result)

    @patch("bluetooth.bt_service._DBUS_AVAILABLE", False)
    def test_disconnect_without_dbus(self):
        from bluetooth.bt_service import BTService
        svc = BTService()
        result = self._run(svc.disconnect("AA:BB:CC:DD:EE:FF"))
        self.assertFalse(result)

    @patch("bluetooth.bt_service._DBUS_AVAILABLE", False)
    def test_forget_without_dbus(self):
        from bluetooth.bt_service import BTService
        svc = BTService()
        result = self._run(svc.forget("AA:BB:CC:DD:EE:FF"))
        self.assertFalse(result)

    def test_stop_cancels_reconnect_tasks(self):
        from bluetooth.bt_service import BTService
        svc = BTService()
        svc._running = True

        # Create mock reconnect tasks
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()
        svc._reconnect_tasks["AA:BB:CC:DD:EE:FF"] = mock_task

        self._run(svc.stop())

        mock_task.cancel.assert_called_once()
        self.assertEqual(svc._reconnect_tasks, {})
        self.assertFalse(svc._running)

    def test_handle_device_props_connected(self):
        from bluetooth.bt_service import BTService, BTState, BTDeviceInfo
        svc = BTService()
        svc._running = True

        # Pre-populate a known device
        info = BTDeviceInfo(address="AA:BB:CC:DD:EE:FF", name="Test", trusted=True)
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info

        # Simulate Connected=True property change
        mock_variant = MagicMock()
        mock_variant.value = True

        svc._handle_device_props_changed(
            "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
            {"Connected": mock_variant}
        )

        self.assertEqual(svc.state, BTState.CONNECTED)
        self.assertIsNotNone(svc.connected_device)
        self.assertEqual(svc.connected_device.address, "AA:BB:CC:DD:EE:FF")

    def test_handle_device_props_disconnected(self):
        from bluetooth.bt_service import BTService, BTState, BTDeviceInfo
        svc = BTService()
        svc._running = True
        svc._state = BTState.CONNECTED

        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="Test",
            trusted=True, connected=True,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info
        svc._connected_device = info

        mock_variant = MagicMock()
        mock_variant.value = False

        disconnect_called = []
        svc.on_disconnect = lambda addr: disconnect_called.append(addr)

        svc._handle_device_props_changed(
            "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
            {"Connected": mock_variant}
        )

        self.assertEqual(svc.state, BTState.DISCONNECTED)
        self.assertIsNone(svc.connected_device)
        self.assertEqual(disconnect_called, ["AA:BB:CC:DD:EE:FF"])

    def test_handle_device_props_new_device_found(self):
        from bluetooth.bt_service import BTService
        svc = BTService()
        svc._running = True

        found_devices = []
        svc.on_device_found = lambda info: found_devices.append(info)

        name_variant = MagicMock()
        name_variant.value = "New Speaker"
        rssi_variant = MagicMock()
        rssi_variant.value = -55

        svc._handle_device_props_changed(
            "/org/bluez/hci0/dev_11_22_33_44_55_66",
            {"Name": name_variant, "RSSI": rssi_variant}
        )

        self.assertIn("11:22:33:44:55:66", svc._known_devices)
        self.assertEqual(svc._known_devices["11:22:33:44:55:66"].name, "New Speaker")
        self.assertEqual(len(found_devices), 1)

    def test_handle_invalid_dbus_path(self):
        from bluetooth.bt_service import BTService
        svc = BTService()
        svc._running = True

        # Should not crash on invalid path
        svc._handle_device_props_changed("/org/bluez/invalid", {})

    def test_parse_device_props_returns_none_for_empty(self):
        from bluetooth.bt_service import BTService
        result = BTService._parse_device_props("/some/path", {})
        self.assertIsNone(result)

    def test_known_devices_is_copy(self):
        from bluetooth.bt_service import BTService, BTDeviceInfo
        svc = BTService()
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = BTDeviceInfo(address="AA:BB:CC:DD:EE:FF")
        kd = svc.known_devices
        kd.pop("AA:BB:CC:DD:EE:FF")
        # Original should be unmodified
        self.assertIn("AA:BB:CC:DD:EE:FF", svc._known_devices)


class TestBTServiceReconnect(unittest.TestCase):
    """Tests for reconnection logic."""

    def test_disconnect_starts_reconnect_for_trusted(self):
        from bluetooth.bt_service import BTService, BTState, BTDeviceInfo
        svc = BTService()
        svc._running = True
        svc._state = BTState.CONNECTED

        # Use a mock to avoid creating actual tasks
        reconnect_calls = []
        svc._start_reconnect = lambda addr: reconnect_calls.append(addr)

        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="AirPods",
            trusted=True, connected=True,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info
        svc._connected_device = info

        mock_variant = MagicMock()
        mock_variant.value = False

        svc._handle_device_props_changed(
            "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
            {"Connected": mock_variant}
        )

        self.assertEqual(reconnect_calls, ["AA:BB:CC:DD:EE:FF"])

    def test_disconnect_no_reconnect_for_untrusted(self):
        from bluetooth.bt_service import BTService, BTState, BTDeviceInfo
        svc = BTService()
        svc._running = True
        svc._state = BTState.CONNECTED

        reconnect_calls = []
        svc._start_reconnect = lambda addr: reconnect_calls.append(addr)

        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="Random",
            trusted=False, connected=True,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info
        svc._connected_device = info

        mock_variant = MagicMock()
        mock_variant.value = False

        svc._handle_device_props_changed(
            "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
            {"Connected": mock_variant}
        )

        self.assertEqual(reconnect_calls, [])


if __name__ == "__main__":
    unittest.main()
