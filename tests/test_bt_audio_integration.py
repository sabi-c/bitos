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


if __name__ == "__main__":
    unittest.main()
