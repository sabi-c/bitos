"""Tests for AAP (Apple Accessory Protocol) client.

All L2CAP/socket interactions are mocked — no real Bluetooth needed.
"""
import os
import sys
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))


class TestAAPPressType(unittest.TestCase):
    """Tests for AAPPressType enum."""

    def test_press_values(self):
        from bluetooth.aap_client import AAPPressType
        self.assertEqual(AAPPressType.SINGLE.value, 0x05)
        self.assertEqual(AAPPressType.DOUBLE.value, 0x06)
        self.assertEqual(AAPPressType.TRIPLE.value, 0x07)
        self.assertEqual(AAPPressType.LONG.value, 0x08)

    def test_press_type_name(self):
        from bluetooth.aap_client import press_type_name
        self.assertEqual(press_type_name(0x05), "single")
        self.assertEqual(press_type_name(0x06), "double")
        self.assertEqual(press_type_name(0x07), "triple")
        self.assertEqual(press_type_name(0x08), "long")
        self.assertEqual(press_type_name(0xFF), "unknown_0xff")


class TestEarState(unittest.TestCase):
    """Tests for EarState enum."""

    def test_ear_states(self):
        from bluetooth.aap_client import EarState
        self.assertEqual(EarState.IN_EAR.value, 0x00)
        self.assertEqual(EarState.OUT_OF_EAR.value, 0x01)
        self.assertEqual(EarState.IN_CASE.value, 0x02)


class TestNoiseControlMode(unittest.TestCase):
    """Tests for NoiseControlMode enum."""

    def test_modes(self):
        from bluetooth.aap_client import NoiseControlMode
        self.assertEqual(NoiseControlMode.OFF.value, 0x01)
        self.assertEqual(NoiseControlMode.ANC.value, 0x02)
        self.assertEqual(NoiseControlMode.TRANSPARENCY.value, 0x03)
        self.assertEqual(NoiseControlMode.ADAPTIVE.value, 0x04)


class TestAAPBatteryStatus(unittest.TestCase):
    """Tests for AAPBatteryStatus dataclass."""

    def test_defaults(self):
        from bluetooth.aap_client import AAPBatteryStatus
        b = AAPBatteryStatus()
        self.assertEqual(b.left, 0)
        self.assertEqual(b.right, 0)
        self.assertEqual(b.case, 0)
        self.assertFalse(b.left_charging)
        self.assertFalse(b.right_charging)
        self.assertFalse(b.case_charging)


class TestAAPEarDetection(unittest.TestCase):
    """Tests for AAPEarDetection dataclass."""

    def test_defaults(self):
        from bluetooth.aap_client import AAPEarDetection, EarState
        e = AAPEarDetection()
        self.assertFalse(e.both_in_ear)
        self.assertTrue(e.both_out)

    def test_both_in_ear(self):
        from bluetooth.aap_client import AAPEarDetection, EarState
        e = AAPEarDetection(primary=EarState.IN_EAR, secondary=EarState.IN_EAR)
        self.assertTrue(e.both_in_ear)
        self.assertFalse(e.both_out)

    def test_one_in_one_out(self):
        from bluetooth.aap_client import AAPEarDetection, EarState
        e = AAPEarDetection(primary=EarState.IN_EAR, secondary=EarState.OUT_OF_EAR)
        self.assertFalse(e.both_in_ear)
        self.assertFalse(e.both_out)

    def test_both_in_case(self):
        from bluetooth.aap_client import AAPEarDetection, EarState
        e = AAPEarDetection(primary=EarState.IN_CASE, secondary=EarState.IN_CASE)
        self.assertFalse(e.both_in_ear)
        self.assertTrue(e.both_out)


class TestAAPClientInit(unittest.TestCase):
    """Tests for AAPClient initialization."""

    def test_initial_state(self):
        from bluetooth.aap_client import AAPClient
        client = AAPClient()
        self.assertIsNone(client.connected_mac)
        self.assertFalse(client.is_connected)
        self.assertIsNone(client.on_stem_press)
        self.assertIsNone(client.on_battery)
        self.assertIsNone(client.on_ear_detect)
        self.assertIsNone(client.on_noise_control)

    def test_disconnect_no_connection(self):
        """Disconnect should be safe when not connected."""
        from bluetooth.aap_client import AAPClient
        client = AAPClient()
        client.disconnect()  # Should not raise
        self.assertIsNone(client.connected_mac)

    @patch("bluetooth.aap_client._BT_AVAILABLE", False)
    def test_connect_without_bluetooth(self):
        from bluetooth.aap_client import AAPClient
        client = AAPClient()
        self.assertFalse(client.is_available)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(client.connect("AA:BB:CC:DD:EE:FF"))
            self.assertFalse(result)
        finally:
            loop.close()


class TestAAPClientPacketParsing(unittest.TestCase):
    """Tests for AAP packet parsing."""

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_parse_battery_packet(self):
        from bluetooth.aap_client import AAPClient, AAP_HEADER_BATTERY

        client = AAPClient()
        battery_events = []
        client.on_battery = lambda l, r, c: battery_events.append((l, r, c))

        # Construct battery packet:
        # header(6) + count(1) + component entries (5 bytes each)
        # 3 components: left(0x01), right(0x02), case(0x04)
        packet = AAP_HEADER_BATTERY + bytes([
            3,           # count
            0x01, 0x01, 85, 0x00, 0x01,   # left: 85%, not charging
            0x02, 0x01, 90, 0x00, 0x01,   # right: 90%, not charging
            0x04, 0x01, 100, 0x01, 0x01,  # case: 100%, charging
        ])

        self._run(client._parse_packet(packet))

        self.assertEqual(client.battery.left, 85)
        self.assertEqual(client.battery.right, 90)
        self.assertEqual(client.battery.case, 100)
        self.assertFalse(client.battery.left_charging)
        self.assertTrue(client.battery.case_charging)
        self.assertEqual(len(battery_events), 1)
        self.assertEqual(battery_events[0], (85, 90, 100))

    def test_parse_ear_detection_packet(self):
        from bluetooth.aap_client import AAPClient, AAP_HEADER_EAR_DETECT, EarState

        client = AAPClient()
        ear_events = []
        client.on_ear_detect = lambda l, r: ear_events.append((l, r))

        # Both in ear
        packet = AAP_HEADER_EAR_DETECT + bytes([0x00, 0x00])
        self._run(client._parse_packet(packet))

        self.assertEqual(client.ear_detection.primary, EarState.IN_EAR)
        self.assertEqual(client.ear_detection.secondary, EarState.IN_EAR)
        self.assertTrue(client.ear_detection.both_in_ear)
        self.assertEqual(len(ear_events), 1)
        self.assertEqual(ear_events[0], (True, True))

    def test_parse_ear_detection_out(self):
        from bluetooth.aap_client import AAPClient, AAP_HEADER_EAR_DETECT, EarState

        client = AAPClient()
        packet = AAP_HEADER_EAR_DETECT + bytes([0x01, 0x02])
        self._run(client._parse_packet(packet))

        self.assertEqual(client.ear_detection.primary, EarState.OUT_OF_EAR)
        self.assertEqual(client.ear_detection.secondary, EarState.IN_CASE)
        self.assertTrue(client.ear_detection.both_out)

    def test_parse_ear_detection_unknown_value(self):
        """Unknown ear state byte should default to OUT_OF_EAR."""
        from bluetooth.aap_client import AAPClient, AAP_HEADER_EAR_DETECT, EarState

        client = AAPClient()
        packet = AAP_HEADER_EAR_DETECT + bytes([0xFF, 0x00])
        self._run(client._parse_packet(packet))

        self.assertEqual(client.ear_detection.primary, EarState.OUT_OF_EAR)
        self.assertEqual(client.ear_detection.secondary, EarState.IN_EAR)

    def test_stem_press_detection(self):
        from bluetooth.aap_client import AAPClient, AAPPressType

        client = AAPClient()
        presses = []
        client.on_stem_press = lambda v: presses.append(v)

        # Packet with single press byte at offset 8
        packet = bytes([0x00] * 8 + [0x05] + [0x00] * 4)
        self._run(client._parse_packet(packet))

        self.assertEqual(len(presses), 1)
        self.assertEqual(presses[0], AAPPressType.SINGLE.value)

    def test_stem_press_double(self):
        from bluetooth.aap_client import AAPClient, AAPPressType

        client = AAPClient()
        presses = []
        client.on_stem_press = lambda v: presses.append(v)

        packet = bytes([0x00] * 10 + [0x06] + [0x00] * 4)
        self._run(client._parse_packet(packet))

        self.assertEqual(len(presses), 1)
        self.assertEqual(presses[0], AAPPressType.DOUBLE.value)

    def test_stem_press_triple(self):
        from bluetooth.aap_client import AAPClient, AAPPressType

        client = AAPClient()
        presses = []
        client.on_stem_press = lambda v: presses.append(v)

        packet = bytes([0x00] * 7 + [0x07] + [0x00] * 4)
        self._run(client._parse_packet(packet))

        self.assertEqual(presses[0], AAPPressType.TRIPLE.value)

    def test_stem_press_long(self):
        from bluetooth.aap_client import AAPClient, AAPPressType

        client = AAPClient()
        presses = []
        client.on_stem_press = lambda v: presses.append(v)

        packet = bytes([0x00] * 9 + [0x08] + [0x00] * 4)
        self._run(client._parse_packet(packet))

        self.assertEqual(presses[0], AAPPressType.LONG.value)

    def test_short_packet_ignored(self):
        """Packets shorter than 6 bytes should be silently ignored."""
        from bluetooth.aap_client import AAPClient

        client = AAPClient()
        presses = []
        client.on_stem_press = lambda v: presses.append(v)

        self._run(client._parse_packet(bytes([0x01, 0x02])))
        self.assertEqual(presses, [])

    def test_battery_short_packet(self):
        """Battery packet with insufficient data should not crash."""
        from bluetooth.aap_client import AAPClient, AAP_HEADER_BATTERY

        client = AAPClient()
        # Header only, no data
        self._run(client._parse_packet(AAP_HEADER_BATTERY))
        self.assertEqual(client.battery.left, 0)

    def test_battery_caps_at_100(self):
        from bluetooth.aap_client import AAPClient, AAP_HEADER_BATTERY

        client = AAPClient()
        packet = AAP_HEADER_BATTERY + bytes([
            1,                              # count
            0x01, 0x01, 200, 0x00, 0x01,   # left: 200% -> capped to 100%
        ])
        self._run(client._parse_packet(packet))
        self.assertEqual(client.battery.left, 100)

    def test_noise_control_parsing(self):
        from bluetooth.aap_client import AAPClient, NoiseControlMode, AAP_HEADER_NOISE_CONTROL

        client = AAPClient()
        nc_events = []
        client.on_noise_control = lambda m: nc_events.append(m)

        # Noise control packet — mode at offset 7
        packet = AAP_HEADER_NOISE_CONTROL[:5] + bytes([0x00, 0x00, 0x02, 0x00, 0x00, 0x00])
        self._run(client._parse_packet(packet))

        self.assertEqual(client.noise_control, NoiseControlMode.ANC)
        self.assertEqual(len(nc_events), 1)


class TestAAPClientDisconnect(unittest.TestCase):
    """Tests for AAP client disconnect behavior."""

    def test_disconnect_clears_state(self):
        from bluetooth.aap_client import AAPClient

        client = AAPClient()
        client._connected_mac = "AA:BB:CC:DD:EE:FF"
        client._running = True

        # Mock socket
        mock_sock = MagicMock()
        client._sock = mock_sock

        # Mock task
        mock_task = MagicMock()
        client._read_task = mock_task

        client.disconnect()

        self.assertIsNone(client.connected_mac)
        self.assertFalse(client._running)
        self.assertIsNone(client._sock)
        self.assertIsNone(client._read_task)
        mock_sock.close.assert_called_once()
        mock_task.cancel.assert_called_once()

    def test_disconnect_handles_socket_error(self):
        from bluetooth.aap_client import AAPClient

        client = AAPClient()
        client._connected_mac = "AA:BB:CC:DD:EE:FF"
        mock_sock = MagicMock()
        mock_sock.close.side_effect = OSError("already closed")
        client._sock = mock_sock

        # Should not raise
        client.disconnect()
        self.assertIsNone(client._sock)


class TestAAPClientFireCallback(unittest.TestCase):
    """Tests for callback dispatch."""

    def test_sync_callback(self):
        from bluetooth.aap_client import AAPClient

        client = AAPClient()
        results = []
        client._fire_callback(lambda x: results.append(x), 42)
        self.assertEqual(results, [42])

    def test_callback_exception_handled(self):
        from bluetooth.aap_client import AAPClient

        client = AAPClient()

        def bad_callback(x):
            raise ValueError("test error")

        # Should not raise
        client._fire_callback(bad_callback, 42)

    def test_async_callback(self):
        from bluetooth.aap_client import AAPClient

        client = AAPClient()
        results = []

        async def async_cb(x):
            results.append(x)

        # The _fire_callback uses ensure_future for coroutines.
        # In a non-running loop, the coroutine won't execute but shouldn't crash.
        client._fire_callback(async_cb, 99)


class TestAAPProtocolConstants(unittest.TestCase):
    """Verify protocol constants match the research document."""

    def test_psm(self):
        from bluetooth.aap_client import AAP_PSM
        self.assertEqual(AAP_PSM, 0x1001)

    def test_handshake_packet(self):
        from bluetooth.aap_client import AAP_HANDSHAKE
        self.assertEqual(AAP_HANDSHAKE, bytes.fromhex("00000400010002000000000000000000"))

    def test_feature_packet(self):
        from bluetooth.aap_client import AAP_SET_FEATURES
        self.assertEqual(AAP_SET_FEATURES, bytes.fromhex("040004004d00ff00000000000000"))

    def test_notification_request(self):
        from bluetooth.aap_client import AAP_REQUEST_NOTIFICATIONS
        self.assertEqual(AAP_REQUEST_NOTIFICATIONS, bytes.fromhex("040004000F00FFFFFFFF"))


if __name__ == "__main__":
    unittest.main()
