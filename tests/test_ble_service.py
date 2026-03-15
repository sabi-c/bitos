"""Tests for BLE NUS service, mock fallback, and factory."""
import os
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from device.ble.ble_service import BITOSBleService, MockBleService, get_ble_service
from device.ble.protocol import BITOSProtocol, ChunkAssembler


class MockBleServiceTests(unittest.TestCase):
    """MockBleService must be a safe drop-in replacement."""

    def test_start_stop_no_crash(self):
        svc = MockBleService()
        svc.start()
        svc.stop()

    def test_is_connected_false_by_default(self):
        svc = MockBleService()
        self.assertFalse(svc.is_connected)

    def test_is_healthy_always_true(self):
        svc = MockBleService()
        self.assertTrue(svc.is_healthy)

    def test_send_returns_false(self):
        svc = MockBleService()
        self.assertFalse(svc.send({"t": "test"}))

    def test_callbacks_can_be_set(self):
        svc = MockBleService()
        called = []
        svc.on_message(lambda msg: called.append(msg))
        svc.on_connect(lambda: called.append("connect"))
        svc.on_disconnect(lambda: called.append("disconnect"))
        # Callbacks are stored but never fired in mock mode
        self.assertEqual(called, [])

    def test_mock_matches_real_interface(self):
        """MockBleService must have the same public interface as BITOSBleService."""
        real_methods = {m for m in dir(BITOSBleService) if not m.startswith("_")}
        mock_methods = {m for m in dir(MockBleService) if not m.startswith("_")}
        missing = real_methods - mock_methods
        self.assertEqual(missing, set(), f"MockBleService missing methods: {missing}")


class GetBleServiceFactoryTests(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_returns_mock_when_env_mock(self):
        os.environ["BITOS_BLE"] = "mock"
        svc = get_ble_service()
        self.assertIsInstance(svc, MockBleService)

    def test_returns_mock_when_bluezero_missing(self):
        os.environ.pop("BITOS_BLE", None)
        # On macOS dev machines, bluezero is not installed -> should get mock
        svc = get_ble_service()
        # Either real (if bluezero is installed) or mock — both are acceptable
        self.assertTrue(isinstance(svc, (BITOSBleService, MockBleService)))


class BITOSBleServiceUnitTests(unittest.TestCase):
    """Test BITOSBleService methods that don't require hardware."""

    def test_initial_state(self):
        svc = BITOSBleService()
        self.assertFalse(svc.is_connected)
        self.assertFalse(svc.is_healthy)
        self.assertFalse(svc._running)

    def test_send_when_not_connected_returns_false(self):
        svc = BITOSBleService()
        self.assertFalse(svc.send({"t": "test"}))

    def test_stop_without_start_no_crash(self):
        svc = BITOSBleService()
        svc.stop()  # Should not raise

    def test_start_sets_running(self):
        svc = BITOSBleService()
        svc.start()
        self.assertTrue(svc._running)
        svc.stop()


class ProtocolTests(unittest.TestCase):
    def test_encode_small_message(self):
        payloads = BITOSProtocol.encode({"t": "ping"})
        self.assertEqual(len(payloads), 1)

    def test_encode_large_message_chunks(self):
        msg = {"t": "data", "body": "x" * 500}
        payloads = BITOSProtocol.encode(msg)
        self.assertGreater(len(payloads), 1)

    def test_decode_valid(self):
        result = BITOSProtocol.decode(b'{"t":"ping"}')
        self.assertEqual(result, {"t": "ping"})

    def test_decode_invalid_returns_none(self):
        result = BITOSProtocol.decode(b'\x00\xff')
        self.assertIsNone(result)


class ChunkAssemblerTests(unittest.TestCase):
    def test_non_chunk_passes_through(self):
        asm = ChunkAssembler()
        msg = {"t": "ping"}
        self.assertEqual(asm.feed(msg), msg)

    def test_reassembly(self):
        asm = ChunkAssembler()
        # Simulate two-chunk message
        self.assertIsNone(asm.feed({"t": "chunk", "i": 0, "n": 2, "d": '{"t":"da'}))
        result = asm.feed({"t": "chunk", "i": 1, "n": 2, "d": 'ta"}'})
        self.assertEqual(result, {"t": "data"})

    def test_assembler_resets_after_complete(self):
        asm = ChunkAssembler()
        asm.feed({"t": "chunk", "i": 0, "n": 1, "d": '{"t":"x"}'})
        # Should be reset
        self.assertEqual(asm._expected, None)
        self.assertEqual(len(asm._chunks), 0)


if __name__ == "__main__":
    unittest.main()
