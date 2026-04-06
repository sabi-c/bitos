"""Tests for BTService + BluetoothAudioManager integration.

Verifies that BTService triggers audio sink switching on connect/disconnect
events via the audio_manager parameter.
"""
import os
import sys
import unittest
import unittest.mock
from unittest.mock import MagicMock
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))


class TestBTServiceAudioManagerIntegration(unittest.TestCase):
    """BTService accepts and uses an audio_manager for sink switching."""

    def test_btservice_accepts_audio_manager(self):
        from bluetooth.bt_service import BTService
        mock_am = MagicMock()
        svc = BTService(audio_manager=mock_am)
        self.assertIs(svc._audio_manager, mock_am)

    def test_btservice_without_audio_manager(self):
        from bluetooth.bt_service import BTService
        svc = BTService()
        self.assertIsNone(svc._audio_manager)

    def test_connect_triggers_sink_switch(self):
        from bluetooth.bt_service import BTService, BTDeviceInfo, BTState
        mock_am = MagicMock()
        svc = BTService(audio_manager=mock_am)
        svc._running = True

        # Pre-populate a known device
        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="AirPods",
            trusted=True, connected=False,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info

        svc._handle_device_connected("AA:BB:CC:DD:EE:FF")

        self.assertEqual(svc.state, BTState.CONNECTED)
        self.assertIsNotNone(svc.connected_device)
        mock_am.switch_sink_to_bt.assert_called_once_with("AA:BB:CC:DD:EE:FF")

    def test_disconnect_triggers_sink_revert(self):
        from bluetooth.bt_service import BTService, BTDeviceInfo, BTState
        mock_am = MagicMock()
        svc = BTService(audio_manager=mock_am)
        svc._running = True
        svc._state = BTState.CONNECTED

        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="AirPods",
            trusted=False, connected=True,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info
        svc._connected_device = info

        # Stub out _start_reconnect to avoid asyncio task creation
        svc._start_reconnect = MagicMock()

        svc._handle_device_disconnected("AA:BB:CC:DD:EE:FF")

        self.assertEqual(svc.state, BTState.DISCONNECTED)
        self.assertIsNone(svc.connected_device)
        mock_am.switch_sink_to_speaker.assert_called_once()

    def test_sink_switch_failure_does_not_crash(self):
        from bluetooth.bt_service import BTService, BTDeviceInfo
        mock_am = MagicMock()
        mock_am.switch_sink_to_bt.side_effect = RuntimeError("PulseAudio exploded")
        svc = BTService(audio_manager=mock_am)
        svc._running = True

        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="Speaker",
            trusted=True, connected=False,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info

        # Should not raise
        svc._handle_device_connected("AA:BB:CC:DD:EE:FF")

        # Service should still be in CONNECTED state despite audio failure
        from bluetooth.bt_service import BTState
        self.assertEqual(svc.state, BTState.CONNECTED)

    def test_disconnect_sink_failure_does_not_crash(self):
        from bluetooth.bt_service import BTService, BTDeviceInfo, BTState
        mock_am = MagicMock()
        mock_am.switch_sink_to_speaker.side_effect = RuntimeError("ALSA broke")
        svc = BTService(audio_manager=mock_am)
        svc._running = True
        svc._state = BTState.CONNECTED

        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="Speaker",
            trusted=False, connected=True,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info
        svc._connected_device = info
        svc._start_reconnect = MagicMock()

        # Should not raise
        svc._handle_device_disconnected("AA:BB:CC:DD:EE:FF")
        self.assertEqual(svc.state, BTState.DISCONNECTED)

    def test_connect_without_audio_manager_works(self):
        """_handle_device_connected works fine when audio_manager is None."""
        from bluetooth.bt_service import BTService, BTDeviceInfo, BTState
        svc = BTService()  # no audio_manager
        svc._running = True

        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="Speaker",
            trusted=True, connected=False,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info

        # Should not raise
        svc._handle_device_connected("AA:BB:CC:DD:EE:FF")
        self.assertEqual(svc.state, BTState.CONNECTED)

    def test_disconnect_without_audio_manager_works(self):
        """_handle_device_disconnected works fine when audio_manager is None."""
        from bluetooth.bt_service import BTService, BTDeviceInfo, BTState
        svc = BTService()  # no audio_manager
        svc._running = True
        svc._state = BTState.CONNECTED

        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="Speaker",
            trusted=False, connected=True,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info
        svc._connected_device = info
        svc._start_reconnect = MagicMock()

        # Should not raise
        svc._handle_device_disconnected("AA:BB:CC:DD:EE:FF")
        self.assertEqual(svc.state, BTState.DISCONNECTED)


    def test_dbus_signal_triggers_sink_switch(self):
        """D-Bus PropertiesChanged signal path triggers audio sink switch."""
        from bluetooth.bt_service import BTService, BTDeviceInfo, BTState, Variant
        mock_am = MagicMock()
        svc = BTService(audio_manager=mock_am)
        svc._running = True

        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="AirPods", trusted=True,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info

        svc._handle_device_props_changed(
            "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
            {"Connected": Variant("b", True)},
        )

        mock_am.switch_sink_to_bt.assert_called_once_with("AA:BB:CC:DD:EE:FF")
        self.assertEqual(svc.state, BTState.CONNECTED)

    def test_dbus_signal_disconnect_triggers_speaker(self):
        """D-Bus disconnect signal reverts audio to speaker."""
        from bluetooth.bt_service import BTService, BTDeviceInfo, BTState, Variant
        mock_am = MagicMock()
        svc = BTService(audio_manager=mock_am)
        svc._running = True
        svc._state = BTState.CONNECTED

        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="AirPods",
            trusted=False, connected=True,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info
        svc._connected_device = info
        svc._start_reconnect = MagicMock()

        svc._handle_device_props_changed(
            "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
            {"Connected": Variant("b", False)},
        )

        mock_am.switch_sink_to_speaker.assert_called_once()
        self.assertEqual(svc.state, BTState.DISCONNECTED)

    def test_connect_fires_on_connect_callback(self):
        """on_connect callback is fired from _handle_device_connected."""
        from bluetooth.bt_service import BTService, BTDeviceInfo
        svc = BTService()
        svc._running = True
        callback = MagicMock()
        svc.on_connect = callback

        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="AirPods", trusted=True,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info

        svc._handle_device_connected("AA:BB:CC:DD:EE:FF")

        callback.assert_called_once()
        args = callback.call_args[0]
        self.assertEqual(args[0], "AA:BB:CC:DD:EE:FF")

    def test_switch_sink_to_bt_accepts_address(self):
        """switch_sink_to_bt(address) creates a device record for ALSA path."""
        from bluetooth.audio_manager import BluetoothAudioManager
        with unittest.mock.patch.object(BluetoothAudioManager, '_check_bluetoothctl', return_value=True), \
             unittest.mock.patch.object(BluetoothAudioManager, '_check_pulseaudio', return_value=False), \
             unittest.mock.patch.object(BluetoothAudioManager, '_switch_audio_to_bt'):
            mgr = BluetoothAudioManager()
            self.assertIsNone(mgr._connected_device)
            mgr.switch_sink_to_bt("AA:BB:CC:DD:EE:FF")
            self.assertIsNotNone(mgr._connected_device)
            self.assertEqual(mgr._connected_device.address, "AA:BB:CC:DD:EE:FF")


class TestACLConnection(unittest.TestCase):
    """Verify _ensure_acl_connection calls hcitool cc before pairing."""

    def test_acl_connection_attempted(self):
        """_ensure_acl_connection calls subprocess.run with hcitool cc."""
        from bluetooth.bt_service import BTService
        with unittest.mock.patch("subprocess.run") as mock_run:
            BTService._ensure_acl_connection("AA:BB:CC:DD:EE:FF")
            mock_run.assert_called_once_with(
                ["sudo", "hcitool", "cc", "AA:BB:CC:DD:EE:FF"],
                capture_output=True, timeout=10,
            )

    def test_acl_connection_graceful_when_hcitool_missing(self):
        """FileNotFoundError from missing hcitool doesn't crash."""
        from bluetooth.bt_service import BTService
        with unittest.mock.patch("subprocess.run", side_effect=FileNotFoundError):
            # Should not raise
            BTService._ensure_acl_connection("AA:BB:CC:DD:EE:FF")


class TestBTServiceRepositoryIntegration(unittest.TestCase):
    """BTService accepts a repository and persists/reads bt_audio_device."""

    def test_btservice_accepts_repository(self):
        from bluetooth.bt_service import BTService
        mock_repo = MagicMock()
        svc = BTService(repository=mock_repo)
        self.assertIs(svc._repository, mock_repo)

    def test_btservice_saves_last_device_on_connect(self):
        from bluetooth.bt_service import BTService, BTDeviceInfo
        mock_repo = MagicMock()
        svc = BTService(repository=mock_repo)
        svc._running = True

        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="AirPods", trusted=True,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info

        svc._handle_device_connected("AA:BB:CC:DD:EE:FF")

        mock_repo.set_setting.assert_called_once_with(
            "bt_audio_device", "AA:BB:CC:DD:EE:FF"
        )

    def test_reconnect_trusted_fallback_to_saved_device(self):
        """When _enumerate_devices returns empty, BTService reads saved device."""
        import asyncio
        from bluetooth.bt_service import BTService

        mock_repo = MagicMock()
        mock_repo.get_setting.return_value = "11:22:33:44:55:66"

        svc = BTService(repository=mock_repo)
        svc._running = True

        # _enumerate_devices returns no devices
        svc._enumerate_devices = unittest.mock.AsyncMock(return_value=[])
        # Capture _start_reconnect calls
        reconnect_calls = []
        svc._start_reconnect = lambda addr: reconnect_calls.append(addr)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(svc._reconnect_trusted())
        finally:
            loop.close()

        mock_repo.get_setting.assert_called_once_with("bt_audio_device")
        self.assertEqual(reconnect_calls, ["11:22:33:44:55:66"])

    def test_reconnect_trusted_no_fallback_when_trusted_found(self):
        """When trusted audio devices exist, repository is NOT consulted."""
        import asyncio
        from bluetooth.bt_service import BTService, BTDeviceInfo, A2DP_SINK_UUID

        mock_repo = MagicMock()

        svc = BTService(repository=mock_repo)
        svc._running = True

        trusted_dev = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="AirPods",
            trusted=True, connected=False, uuids=[A2DP_SINK_UUID],
        )
        svc._enumerate_devices = unittest.mock.AsyncMock(return_value=[trusted_dev])
        reconnect_calls = []
        svc._start_reconnect = lambda addr: reconnect_calls.append(addr)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(svc._reconnect_trusted())
        finally:
            loop.close()

        # Should reconnect the trusted device, NOT consult repository
        self.assertEqual(reconnect_calls, ["AA:BB:CC:DD:EE:FF"])
        mock_repo.get_setting.assert_not_called()

    def test_save_device_failure_does_not_crash(self):
        """Repository.set_setting failure is logged, not raised."""
        from bluetooth.bt_service import BTService, BTDeviceInfo
        mock_repo = MagicMock()
        mock_repo.set_setting.side_effect = RuntimeError("DB locked")

        svc = BTService(repository=mock_repo)
        svc._running = True

        info = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:FF", name="AirPods", trusted=True,
        )
        svc._known_devices["AA:BB:CC:DD:EE:FF"] = info

        # Should not raise
        svc._handle_device_connected("AA:BB:CC:DD:EE:FF")
        from bluetooth.bt_service import BTState
        self.assertEqual(svc.state, BTState.CONNECTED)


class TestAudioFiltering(unittest.TestCase):
    """BTService._filter_audio_devices returns only audio-capable devices."""

    def test_filter_audio_devices(self):
        """Only devices with A2DP UUID pass; keyboards and unnamed devices are excluded."""
        from bluetooth.bt_service import BTService, BTDeviceInfo, A2DP_SINK_UUID

        audio_dev = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:01", name="Sony WH-1000XM5",
            uuids=[A2DP_SINK_UUID],
        )
        keyboard = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:02", name="Logitech K380",
            uuids=["00001124-0000-1000-8000-00805f9b34fb"],  # HID UUID
        )
        unnamed = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:03", name="Unknown",
        )

        result = BTService._filter_audio_devices([audio_dev, keyboard, unnamed])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].address, "AA:BB:CC:DD:EE:01")

    def test_filter_includes_airpods_without_uuid(self):
        """AirPods are detected by name even when no A2DP UUID is advertised."""
        from bluetooth.bt_service import BTService, BTDeviceInfo

        airpods = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:04", name="AirPods Pro",
            uuids=[],  # No UUIDs advertised yet
        )
        keyboard = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:05", name="Apple Keyboard",
        )

        result = BTService._filter_audio_devices([airpods, keyboard])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].address, "AA:BB:CC:DD:EE:04")
        self.assertTrue(result[0].is_airpods)

    def test_filter_includes_keyword_match(self):
        """Devices with audio keywords in name pass even without UUIDs."""
        from bluetooth.bt_service import BTService, BTDeviceInfo

        jbl = BTDeviceInfo(
            address="AA:BB:CC:DD:EE:06", name="JBL Flip 6",
            uuids=[],
        )
        result = BTService._filter_audio_devices([jbl])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].address, "AA:BB:CC:DD:EE:06")

    def test_filter_empty_list(self):
        """Empty input returns empty output."""
        from bluetooth.bt_service import BTService
        self.assertEqual(BTService._filter_audio_devices([]), [])


class TestBTSecurityPolicy(unittest.TestCase):
    """Security: trust is only set during explicit pairing."""

    def test_trust_call_inside_not_paired_block(self):
        """Verify trust is set conditionally in pair_and_connect source."""
        import inspect
        from bluetooth.bt_service import BTService
        source = inspect.getsource(BTService.pair_and_connect)
        # Find the trust line and verify it's indented inside the not-paired block
        lines = source.split('\n')
        trust_line_idx = None
        not_paired_idx = None
        for i, line in enumerate(lines):
            if 'not paired.value' in line:
                not_paired_idx = i
            # call_set and "Trusted" may be split across continuation lines
            if '"Trusted"' in line:
                trust_line_idx = i
        self.assertIsNotNone(trust_line_idx, "Trust call not found in pair_and_connect")
        self.assertIsNotNone(not_paired_idx, "not paired check not found")
        # Trust must come after the not-paired check
        self.assertGreater(trust_line_idx, not_paired_idx)
        # Verify trust line is indented MORE than the not-paired check
        # (i.e., it's inside the if block, not at the same level)
        not_paired_indent = len(lines[not_paired_idx]) - len(lines[not_paired_idx].lstrip())
        trust_indent = len(lines[trust_line_idx]) - len(lines[trust_line_idx].lstrip())
        self.assertGreater(
            trust_indent, not_paired_indent,
            "Trust call must be indented inside the 'if not paired' block"
        )


if __name__ == "__main__":
    unittest.main()
