"""Tests for the Open Interpreter 01-compatible WebSocket endpoint."""

import json
import struct
import os
import wave
import tempfile

import pytest

# Import the module under test
from server.endpoints.ws_01_compat import (
    parse_01_message,
    is_start_message,
    is_end_message,
    pcm_to_wav,
    wav_to_pcm,
    resample_pcm,
    INPUT_SAMPLE_RATE,
    OUTPUT_SAMPLE_RATE,
)


# ── parse_01_message ─────────────────────────────────────────────────

class TestParse01Message:
    def test_parse_json_string(self):
        raw = '{"role": "user", "type": "message", "start": true}'
        result = parse_01_message(raw)
        assert result == {"role": "user", "type": "message", "start": True}

    def test_parse_json_bytes(self):
        raw = b'{"role": "user", "type": "audio", "end": true}'
        result = parse_01_message(raw)
        assert result == {"role": "user", "type": "audio", "end": True}

    def test_raw_audio_bytes_returns_none(self):
        # Random PCM audio data should not parse as JSON
        raw = struct.pack("<10h", *range(10))
        result = parse_01_message(raw)
        assert result is None

    def test_invalid_json_string_returns_none(self):
        result = parse_01_message("not json at all")
        assert result is None

    def test_empty_string(self):
        result = parse_01_message("")
        assert result is None

    def test_content_message(self):
        raw = '{"role": "user", "type": "message", "content": "Hello"}'
        result = parse_01_message(raw)
        assert result["content"] == "Hello"


# ── is_start_message / is_end_message ────────────────────────────────

class TestStartEndMessages:
    def test_start_message_audio(self):
        msg = {"role": "user", "type": "audio", "format": "bytes.raw", "start": True}
        assert is_start_message(msg) is True
        assert is_end_message(msg) is False

    def test_end_message_audio(self):
        msg = {"role": "user", "type": "audio", "format": "bytes.raw", "end": True}
        assert is_end_message(msg) is True
        assert is_start_message(msg) is False

    def test_start_message_generic(self):
        msg = {"role": "user", "type": "message", "start": True}
        assert is_start_message(msg) is True

    def test_end_message_generic(self):
        msg = {"role": "user", "type": "message", "end": True}
        assert is_end_message(msg) is True

    def test_assistant_message_not_start(self):
        msg = {"role": "assistant", "type": "message", "start": True}
        assert is_start_message(msg) is False

    def test_missing_role(self):
        msg = {"type": "audio", "start": True}
        assert is_start_message(msg) is False

    def test_start_false(self):
        msg = {"role": "user", "type": "audio", "start": False}
        assert is_start_message(msg) is False

    def test_empty_dict(self):
        assert is_start_message({}) is False
        assert is_end_message({}) is False


# ── pcm_to_wav / wav_to_pcm roundtrip ───────────────────────────────

class TestPcmWavRoundtrip:
    def test_roundtrip(self):
        # Generate 100 samples of 16-bit PCM
        samples = list(range(-50, 50))
        pcm_in = struct.pack(f"<{len(samples)}h", *samples)

        wav_path = pcm_to_wav(pcm_in)
        try:
            assert os.path.exists(wav_path)
            assert wav_path.endswith(".wav")

            # Verify WAV properties
            with wave.open(wav_path, "rb") as wf:
                assert wf.getnchannels() == 1
                assert wf.getsampwidth() == 2
                assert wf.getframerate() == INPUT_SAMPLE_RATE
                assert wf.getnframes() == len(samples)

            # Roundtrip
            pcm_out = wav_to_pcm(wav_path)
            assert pcm_out == pcm_in
        finally:
            os.unlink(wav_path)

    def test_empty_pcm(self):
        wav_path = pcm_to_wav(b"")
        try:
            with wave.open(wav_path, "rb") as wf:
                assert wf.getnframes() == 0
        finally:
            os.unlink(wav_path)


# ── resample_pcm ─────────────────────────────────────────────────────

class TestResamplePcm:
    def test_same_rate_passthrough(self):
        pcm = struct.pack("<5h", 1, 2, 3, 4, 5)
        result = resample_pcm(pcm, 16000, 16000)
        assert result == pcm

    def test_upsample_length(self):
        # 100 samples at 16 kHz -> should be ~150 samples at 24 kHz
        samples = list(range(100))
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        result = resample_pcm(pcm, 16000, 24000)
        out_samples = struct.unpack(f"<{len(result) // 2}h", result)
        expected_len = int(100 * 24000 / 16000)
        assert len(out_samples) == expected_len

    def test_downsample_length(self):
        samples = list(range(150))
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        result = resample_pcm(pcm, 24000, 16000)
        out_samples = struct.unpack(f"<{len(result) // 2}h", result)
        expected_len = int(150 * 16000 / 24000)
        assert len(out_samples) == expected_len

    def test_clipping_protection(self):
        # Values near int16 max should not overflow
        samples = [32767, -32768, 0]
        pcm = struct.pack("<3h", *samples)
        result = resample_pcm(pcm, 16000, 24000)
        out_samples = struct.unpack(f"<{len(result) // 2}h", result)
        for s in out_samples:
            assert -32768 <= s <= 32767

    def test_empty_input(self):
        result = resample_pcm(b"", 16000, 24000)
        assert result == b""


# ── Protocol message construction ────────────────────────────────────

class TestProtocolMessages:
    """Test that we can construct valid 01 protocol messages."""

    def test_assistant_start_message(self):
        msg = {
            "role": "assistant",
            "type": "audio",
            "format": "bytes.raw",
            "start": True,
        }
        encoded = json.dumps(msg)
        decoded = json.loads(encoded)
        assert decoded["role"] == "assistant"
        assert decoded["start"] is True

    def test_assistant_text_content(self):
        msg = {
            "role": "assistant",
            "type": "message",
            "content": "Hello from BITOS",
        }
        encoded = json.dumps(msg)
        decoded = json.loads(encoded)
        assert decoded["content"] == "Hello from BITOS"

    def test_assistant_end_message(self):
        msg = {
            "role": "assistant",
            "type": "audio",
            "format": "bytes.raw",
            "end": True,
        }
        encoded = json.dumps(msg)
        decoded = json.loads(encoded)
        assert decoded["end"] is True
