"""Tests for AudioRouter — routing decisions, mode switching, ducking."""
import os
import sys
import threading

import pytest

# Ensure device/ is on path
DEVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "device")
if DEVICE_DIR not in sys.path:
    sys.path.insert(0, DEVICE_DIR)


class MockBTAudioManager:
    """Minimal mock of BluetoothAudioManager for AudioRouter tests."""

    def __init__(self, bt_routed: bool = False):
        self._bt_routed = bt_routed

    def is_audio_routed_to_bt(self) -> bool:
        return self._bt_routed


class TestAudioRouter:
    def _make_router(self, bt_routed: bool = False, repo=None):
        from bluetooth.audio_router import AudioRouter
        bt = MockBTAudioManager(bt_routed=bt_routed)
        return AudioRouter(bt, repository=repo)

    def test_initial_state(self):
        router = self._make_router()
        assert router.airpod_mode is False
        assert router.output_device == "speaker"
        assert router.input_device == "wm8960"
        assert router.is_ducked is False
        assert router.device_type is None

    def test_output_headphones_when_bt_routed(self):
        router = self._make_router(bt_routed=True)
        assert router.output_device == "headphones"

    def test_enter_airpod_mode(self):
        router = self._make_router()
        router.enter_airpod_mode()
        assert router.airpod_mode is True
        assert router.output_device == "airpods"
        assert router.device_type == "airpods"

    def test_exit_airpod_mode(self):
        router = self._make_router()
        router.enter_airpod_mode()
        router.exit_airpod_mode()
        assert router.airpod_mode is False
        assert router.device_type is None

    def test_input_default_wm8960(self):
        router = self._make_router()
        router.enter_airpod_mode()
        # Default: mic stays on wm8960 even in airpod mode
        assert router.input_device == "wm8960"

    def test_input_airpod_hfp_when_enabled(self):
        router = self._make_router()
        router.enter_airpod_mode()
        router.set_airpod_mic(True)
        assert router.input_device == "airpods_hfp"

    def test_input_wm8960_when_mic_disabled(self):
        router = self._make_router()
        router.enter_airpod_mode()
        router.set_airpod_mic(True)
        router.set_airpod_mic(False)
        assert router.input_device == "wm8960"

    def test_on_bt_connect_airpods(self):
        router = self._make_router()
        router.on_bt_connect("AA:BB:CC:DD:EE:FF", {"name": "Seb's AirPods Pro"})
        assert router.airpod_mode is True
        assert router.device_type == "airpods"

    def test_on_bt_connect_generic_headphones(self):
        router = self._make_router()
        router.on_bt_connect("AA:BB:CC:DD:EE:FF", {"name": "Sony WH-1000XM5"})
        assert router.airpod_mode is False
        assert router.device_type == "headphones"

    def test_on_bt_disconnect(self):
        router = self._make_router()
        router.enter_airpod_mode()
        router.on_bt_disconnect("AA:BB:CC:DD:EE:FF")
        assert router.airpod_mode is False
        assert router.device_type is None

    def test_duck_and_restore(self, monkeypatch):
        router = self._make_router()
        # Mock the pactl call
        calls = []
        monkeypatch.setattr(
            "bluetooth.audio_router.AudioRouter._set_sink_volume",
            lambda self, v: calls.append(v) or True,
        )
        monkeypatch.setattr("bluetooth.audio_router._FADE_INTERVAL_S", 0)

        router.duck_audio(15)
        assert router.is_ducked is True
        assert len(calls) > 0
        assert calls[-1] == 15

        calls.clear()
        router.restore_audio(100)
        assert router.is_ducked is False
        assert calls[-1] == 100

    def test_duck_idempotent(self, monkeypatch):
        router = self._make_router()
        calls = []
        monkeypatch.setattr(
            "bluetooth.audio_router.AudioRouter._set_sink_volume",
            lambda self, v: calls.append(v) or True,
        )
        monkeypatch.setattr("bluetooth.audio_router._FADE_INTERVAL_S", 0)

        router.duck_audio(15)
        first_count = len(calls)
        router.duck_audio(15)  # Should be no-op
        assert len(calls) == first_count

    def test_restore_without_duck_is_noop(self, monkeypatch):
        router = self._make_router()
        calls = []
        monkeypatch.setattr(
            "bluetooth.audio_router.AudioRouter._set_sink_volume",
            lambda self, v: calls.append(v) or True,
        )
        router.restore_audio(100)
        assert len(calls) == 0

    def test_exit_airpod_mode_restores_if_ducked(self, monkeypatch):
        router = self._make_router()
        calls = []
        monkeypatch.setattr(
            "bluetooth.audio_router.AudioRouter._set_sink_volume",
            lambda self, v: calls.append(v) or True,
        )
        monkeypatch.setattr("bluetooth.audio_router._FADE_INTERVAL_S", 0)

        router.enter_airpod_mode()
        router.duck_audio(15)
        calls.clear()

        router.exit_airpod_mode()
        # Should have called set_sink_volume to restore
        assert any(v == 100 for v in calls)

    def test_get_status(self):
        router = self._make_router()
        status = router.get_status()
        assert "output" in status
        assert "input" in status
        assert "airpod_mode" in status
        assert "ducked" in status
        assert status["output"] == "speaker"
        assert status["ducked"] is False


class TestDetectDeviceType:
    def test_airpods(self):
        from bluetooth.audio_router import detect_device_type
        assert detect_device_type("Seb's AirPods Pro") == "airpods"
        assert detect_device_type("AirPods Max") == "airpods"
        assert detect_device_type("AIRPODS") == "airpods"

    def test_speakers(self):
        from bluetooth.audio_router import detect_device_type
        assert detect_device_type("JBL Flip 6") == "speaker"
        assert detect_device_type("Sonos Roam") == "speaker"
        assert detect_device_type("Echo Dot") == "speaker"
        assert detect_device_type("My Speaker") == "speaker"

    def test_headphones(self):
        from bluetooth.audio_router import detect_device_type
        assert detect_device_type("Sony WH-1000XM5") == "headphones"
        assert detect_device_type("Bose QC45") == "headphones"
        assert detect_device_type("Unknown Device") == "headphones"
