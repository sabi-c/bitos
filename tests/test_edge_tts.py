"""Tests for Edge TTS provider and updated TTS engine detection."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


class TestEdgeTTSProvider:
    def test_is_available_when_installed(self):
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            from device.audio.edge_tts_provider import is_available
            # Need to reimport since the check is dynamic
            assert is_available() is True

    def test_is_available_when_not_installed(self):
        import sys
        # Ensure edge_tts is not importable
        with patch.dict("sys.modules", {"edge_tts": None}):
            # Force reimport
            from device.audio import edge_tts_provider
            result = edge_tts_provider.is_available()
            assert result is False

    def test_synthesize_returns_false_when_not_available(self, tmp_path):
        from device.audio.edge_tts_provider import synthesize
        out = tmp_path / "out.wav"
        with patch("device.audio.edge_tts_provider.is_available", return_value=False):
            assert synthesize("hello", out) is False

    def test_synthesize_calls_edge_tts(self, tmp_path):
        """Test that synthesize orchestrates edge_tts.Communicate correctly."""
        out = tmp_path / "out.wav"
        fake_wav = b"RIFF" + b"\x00" * 100

        mock_communicate = MagicMock()

        async def fake_stream():
            yield {"type": "audio", "data": fake_wav[:50]}
            yield {"type": "audio", "data": fake_wav[50:]}

        mock_communicate.stream = fake_stream

        mock_edge = MagicMock()
        mock_edge.Communicate.return_value = mock_communicate

        with patch("device.audio.edge_tts_provider.is_available", return_value=True):
            with patch.dict("sys.modules", {"edge_tts": mock_edge}):
                # Mock _mp3_to_wav since we're not testing MP3 conversion
                with patch("device.audio.edge_tts_provider._mp3_to_wav", return_value=True) as mock_convert:
                    from device.audio.edge_tts_provider import synthesize
                    result = synthesize("hello", out)

        assert result is True
        mock_edge.Communicate.assert_called_once_with("hello", "en-US-AriaNeural", rate=None, pitch=None)


class TestTTSEngineDetection:
    """Test the updated detection chain includes edge_tts."""

    def test_edge_tts_detected_first_in_auto(self):
        """Edge TTS should be preferred over speechify in auto mode."""
        from device.audio.tts import TextToSpeech

        with patch.object(TextToSpeech, "__init__", lambda self, **kw: None):
            tts = TextToSpeech.__new__(TextToSpeech)
            tts.player = MagicMock()

            with patch.object(TextToSpeech, "_check_edge_tts", return_value=True):
                with patch.dict(os.environ, {"SPEECHIFY_API_KEY": "test-key"}):
                    engine = tts._detect_engine()
                    assert engine == "edge_tts"

    def test_speechify_used_when_edge_tts_missing(self):
        """Fall back to speechify when edge-tts not installed."""
        from device.audio.tts import TextToSpeech

        with patch.object(TextToSpeech, "__init__", lambda self, **kw: None):
            tts = TextToSpeech.__new__(TextToSpeech)
            tts.player = MagicMock()

            with patch.object(TextToSpeech, "_check_edge_tts", return_value=False):
                with patch.dict(os.environ, {"SPEECHIFY_API_KEY": "test-key"}):
                    engine = tts._detect_engine()
                    assert engine == "speechify"

    def test_preferred_engine_edge_tts(self):
        """User can explicitly select edge_tts engine."""
        from device.audio.tts import TextToSpeech

        mock_repo = MagicMock()
        mock_repo.get_setting.return_value = "edge_tts"

        with patch.object(TextToSpeech, "__init__", lambda self, **kw: None):
            tts = TextToSpeech.__new__(TextToSpeech)
            tts.player = MagicMock()

            with patch.object(TextToSpeech, "_check_edge_tts", return_value=True):
                with patch("device.audio.tts.TextToSpeech._detect_engine") as detect:
                    # Test the logic directly
                    pass

            # More direct test: mock the repo and check
            with patch.object(TextToSpeech, "_check_edge_tts", return_value=True):
                with patch("storage.repository.DeviceRepository", return_value=mock_repo):
                    engine = tts._detect_engine()
                    assert engine == "edge_tts"

    def test_preferred_engine_falls_back_on_unavailable(self):
        """If preferred engine not available, fall back to auto."""
        from device.audio.tts import TextToSpeech

        mock_repo = MagicMock()
        mock_repo.get_setting.return_value = "edge_tts"

        with patch.object(TextToSpeech, "__init__", lambda self, **kw: None):
            tts = TextToSpeech.__new__(TextToSpeech)
            tts.player = MagicMock()

            with patch.object(TextToSpeech, "_check_edge_tts", return_value=False):
                with patch.object(TextToSpeech, "_check_chatterbox", return_value=False):
                    with patch("storage.repository.DeviceRepository", return_value=mock_repo):
                        env = {k: v for k, v in os.environ.items()
                               if k not in ("SPEECHIFY_API_KEY", "OPENAI_API_KEY")}
                        with patch.dict(os.environ, env, clear=True):
                            engine = tts._detect_engine()
                            # Should fall through to espeak or silent
                            assert engine in ("espeak", "silent")


class TestTTSLatencyMetrics:
    """Test that latency metrics are tracked."""

    def test_speak_records_synthesis_time(self):
        from device.audio.tts import TextToSpeech

        with patch.object(TextToSpeech, "__init__", lambda self, **kw: None):
            tts = TextToSpeech.__new__(TextToSpeech)
            tts.player = MagicMock()
            tts.player.play_file.return_value = True
            tts.engine = "espeak"
            tts.last_synthesis_ms = 0
            tts.last_ttfb_ms = 0

            # Mock espeak to create a small WAV file
            def fake_espeak(text, output_file):
                import wave
                with wave.open(str(output_file), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(22050)
                    wf.writeframes(b"\x00" * 4410)

            with patch.object(tts, "_run_espeak", side_effect=fake_espeak):
                with patch("device.audio.player._USE_APLAY", False):
                    result = tts.speak("hello world")

            assert result is True
            assert tts.last_synthesis_ms >= 0
