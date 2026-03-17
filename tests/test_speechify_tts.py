"""Tests for Speechify TTS integration."""
import base64
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from device.audio.speechify import synthesize, get_api_key


class TestGetApiKey:
    def test_returns_key_when_set(self):
        with patch.dict(os.environ, {"SPEECHIFY_API_KEY": "test-key"}):
            assert get_api_key() == "test-key"

    def test_returns_none_when_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            assert get_api_key() is None


class TestSynthesize:
    def test_returns_false_without_api_key(self, tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            assert synthesize("hello", tmp_path / "out.wav") is False

    def test_successful_synthesis(self, tmp_path):
        fake_wav = b"RIFF" + b"\x00" * 100
        fake_response = {
            "audio_data": base64.b64encode(fake_wav).decode(),
            "audio_format": "wav",
            "billable_characters_count": 5,
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_response
        mock_resp.raise_for_status = MagicMock()

        out = tmp_path / "out.wav"
        with patch.dict(os.environ, {"SPEECHIFY_API_KEY": "test-key"}):
            with patch("device.audio.speechify.httpx.post", return_value=mock_resp) as mock_post:
                result = synthesize("hello", out)

        assert result is True
        assert out.exists()
        assert out.read_bytes() == fake_wav

        # Verify API call
        call_args = mock_post.call_args
        assert "Bearer test-key" in call_args.kwargs["headers"]["Authorization"]
        body = call_args.kwargs["json"]
        assert body["input"] == "hello"
        assert body["voice_id"] == "sophia"
        assert body["audio_format"] == "wav"

    def test_returns_false_on_empty_audio(self, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"audio_data": "", "audio_format": "wav"}
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"SPEECHIFY_API_KEY": "test-key"}):
            with patch("device.audio.speechify.httpx.post", return_value=mock_resp):
                assert synthesize("hello", tmp_path / "out.wav") is False

    def test_returns_false_on_timeout(self, tmp_path):
        import httpx
        with patch.dict(os.environ, {"SPEECHIFY_API_KEY": "test-key"}):
            with patch("device.audio.speechify.httpx.post", side_effect=httpx.TimeoutException("timeout")):
                assert synthesize("hello", tmp_path / "out.wav") is False

    def test_returns_false_on_http_error(self, tmp_path):
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_resp
        )
        with patch.dict(os.environ, {"SPEECHIFY_API_KEY": "test-key"}):
            with patch("device.audio.speechify.httpx.post", return_value=mock_resp):
                assert synthesize("hello", tmp_path / "out.wav") is False

    def test_custom_voice_id(self, tmp_path):
        fake_response = {
            "audio_data": base64.b64encode(b"wav-data").decode(),
            "audio_format": "wav",
            "billable_characters_count": 5,
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_response
        mock_resp.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"SPEECHIFY_API_KEY": "test-key"}):
            with patch("device.audio.speechify.httpx.post", return_value=mock_resp) as mock_post:
                synthesize("hello", tmp_path / "out.wav", voice_id="george")

        body = mock_post.call_args.kwargs["json"]
        assert body["voice_id"] == "george"


class TestTTSFallbackChain:
    def test_speechify_detected_as_engine(self):
        from device.audio.tts import TextToSpeech
        with patch.dict(os.environ, {"SPEECHIFY_API_KEY": "test-key"}):
            with patch.object(TextToSpeech, "__init__", lambda self, **kw: None):
                tts = TextToSpeech.__new__(TextToSpeech)
                tts.player = MagicMock()
                # When edge_tts is not available, speechify should be detected
                with patch.object(TextToSpeech, "_check_edge_tts", return_value=False):
                    assert tts._detect_engine() == "speechify"

    def test_speechify_not_detected_without_key(self):
        from device.audio.tts import TextToSpeech
        env = {k: v for k, v in os.environ.items() if k != "SPEECHIFY_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(TextToSpeech, "__init__", lambda self, **kw: None):
                tts = TextToSpeech.__new__(TextToSpeech)
                tts.player = MagicMock()
                engine = tts._detect_engine()
                assert engine != "speechify"
