"""Tests for BluetoothAudioManager sink switching and device detection.

All subprocess calls (bluetoothctl, pactl) are mocked since we can't test
real Bluetooth or PulseAudio in CI.
"""
import os
import sys
import subprocess
import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))


def _make_manager(**overrides):
    """Create a BluetoothAudioManager with bluetoothctl/pulseaudio checks mocked."""
    defaults = {
        "bluetooth.audio_manager.BluetoothAudioManager._check_bluetoothctl": True,
        "bluetooth.audio_manager.BluetoothAudioManager._check_pulseaudio": True,
    }
    defaults.update(overrides)
    patches = {k: patch(k, return_value=v) for k, v in defaults.items()}
    for p in patches.values():
        p.start()
    from bluetooth.audio_manager import BluetoothAudioManager
    mgr = BluetoothAudioManager(repository=None)
    for p in patches.values():
        p.stop()
    return mgr


class TestInitWithoutBluetooth(unittest.TestCase):
    """test_init_without_bluetooth -- manager initialises when bluetoothctl unavailable."""

    def test_init_without_bluetooth(self):
        mgr = _make_manager(
            **{"bluetooth.audio_manager.BluetoothAudioManager._check_bluetoothctl": False}
        )
        self.assertFalse(mgr._bt_available)
        # Should still have a valid object
        self.assertIsNone(mgr.get_connected_device())


class TestSwitchSinkToBtFindsBluezSink(unittest.TestCase):
    """test_switch_sink_to_bt_finds_bluez_sink -- mock pactl, verify it finds and sets bluez sink."""

    @patch("subprocess.run")
    def test_switch_sink_to_bt_finds_bluez_sink(self, mock_run):
        mgr = _make_manager()
        # pactl list short sinks output
        list_result = MagicMock(
            returncode=0,
            stdout="1\talsa_output.pci\tmodule-alsa\tIDLE\n2\tbluez_sink.AA_BB_CC\tmodule-bluez\tIDLE\n",
        )
        set_result = MagicMock(returncode=0)
        # list sink-inputs (for _move_streams_to_sink)
        inputs_result = MagicMock(returncode=0, stdout="")

        mock_run.side_effect = [list_result, set_result, inputs_result]

        mgr._switch_audio_to_bt_pulse()

        # The second call should be pactl set-default-sink with the bluez sink
        calls = mock_run.call_args_list
        self.assertEqual(calls[1][0][0], ["pactl", "set-default-sink", "bluez_sink.AA_BB_CC"])


class TestSwitchSinkToSpeakerAvoidsBluez(unittest.TestCase):
    """test_switch_sink_to_speaker_avoids_bluez -- mock pactl, verify it picks non-bluez sink."""

    @patch("subprocess.run")
    def test_switch_sink_to_speaker_avoids_bluez(self, mock_run):
        mgr = _make_manager()
        list_result = MagicMock(
            returncode=0,
            stdout="1\tbluez_sink.AA_BB_CC\tmodule-bluez\tIDLE\n2\talsa_output.pci\tmodule-alsa\tIDLE\n",
        )
        set_result = MagicMock(returncode=0)
        inputs_result = MagicMock(returncode=0, stdout="")

        mock_run.side_effect = [list_result, set_result, inputs_result]

        mgr._switch_audio_to_speaker_pulse()

        calls = mock_run.call_args_list
        self.assertEqual(calls[1][0][0], ["pactl", "set-default-sink", "alsa_output.pci"])


class TestIsAudioRoutedToBt(unittest.TestCase):
    """test_is_audio_routed_to_bt_true / false -- mock pactl get-default-sink."""

    @patch("subprocess.run")
    def test_is_audio_routed_to_bt_true(self, mock_run):
        mgr = _make_manager()
        mock_run.return_value = MagicMock(returncode=0, stdout="bluez_sink.AA_BB_CC_DD_EE_FF\n")
        self.assertTrue(mgr.is_audio_routed_to_bt())

    @patch("subprocess.run")
    def test_is_audio_routed_to_bt_false(self, mock_run):
        mgr = _make_manager()
        mock_run.return_value = MagicMock(returncode=0, stdout="alsa_output.pci-0000_00_1f.3.analog-stereo\n")
        self.assertFalse(mgr.is_audio_routed_to_bt())


class TestDetectDeviceType(unittest.TestCase):
    """test_detect_device_type_airpods / speaker / headphones."""

    def _mgr_with_device_info(self, name: str):
        mgr = _make_manager()
        mgr._get_device_info = MagicMock(return_value={"Name": name})
        return mgr

    def test_detect_device_type_airpods(self):
        mgr = self._mgr_with_device_info("AirPods Pro (Seb)")
        self.assertEqual(mgr.detect_device_type("AA:BB:CC:DD:EE:FF"), "airpods")

    def test_detect_device_type_speaker(self):
        mgr = self._mgr_with_device_info("JBL Flip 5")
        self.assertEqual(mgr.detect_device_type("AA:BB:CC:DD:EE:FF"), "speaker")

    def test_detect_device_type_headphones(self):
        mgr = self._mgr_with_device_info("Sony WH-1000XM4")
        self.assertEqual(mgr.detect_device_type("AA:BB:CC:DD:EE:FF"), "headphones")


class TestPublicSwitchMethodsExist(unittest.TestCase):
    """test_public_switch_methods_exist -- verify switch_sink_to_bt and switch_sink_to_speaker exist."""

    def test_public_switch_methods_exist(self):
        mgr = _make_manager()
        self.assertTrue(callable(getattr(mgr, "switch_sink_to_bt", None)))
        self.assertTrue(callable(getattr(mgr, "switch_sink_to_speaker", None)))


class TestSwitchSinkToBtWithAddressCreatesDevice(unittest.TestCase):
    """test_switch_sink_to_bt_with_address_creates_device -- verify ALSA path fix works."""

    @patch("subprocess.run")
    def test_switch_sink_to_bt_with_address_creates_device(self, mock_run):
        # Use a manager without PulseAudio so it takes the ALSA path
        mgr = _make_manager(
            **{"bluetooth.audio_manager.BluetoothAudioManager._check_pulseaudio": False}
        )
        self.assertIsNone(mgr._connected_device)

        # Patch the ALSA write to avoid touching the filesystem
        with patch.object(mgr, "_switch_audio_to_bt_alsa") as mock_alsa:
            mgr.switch_sink_to_bt(address="AA:BB:CC:DD:EE:FF")

        # A device record should now exist
        self.assertIsNotNone(mgr._connected_device)
        self.assertEqual(mgr._connected_device.address, "AA:BB:CC:DD:EE:FF")
        self.assertTrue(mgr._connected_device.connected)


if __name__ == "__main__":
    unittest.main()
