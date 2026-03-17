import os
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import struct

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from audio.pipeline import MockAudioPipeline, WM8960Pipeline, get_audio_pipeline

try:
    from audio.recorder import AudioRecorder
except ImportError:
    AudioRecorder = None


class AudioWM8960Tests(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("BITOS_AUDIO")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("BITOS_AUDIO", None)
        else:
            os.environ["BITOS_AUDIO"] = self._prev

    def test_factory_returns_mock_pipeline_for_mock_mode(self):
        os.environ["BITOS_AUDIO"] = "mock"
        self.assertIsInstance(get_audio_pipeline(), MockAudioPipeline)

    def test_factory_returns_wm8960_pipeline_for_hw_mode(self):
        os.environ["BITOS_AUDIO"] = "hw:0"
        self.assertIsInstance(get_audio_pipeline(), WM8960Pipeline)

    def test_wm8960_pipeline_reports_available(self):
        self.assertTrue(WM8960Pipeline().is_available())

    def test_mock_record_returns_a_path_string(self):
        p = MockAudioPipeline()
        out = p.record()
        self.assertIsInstance(out, str)
        self.assertTrue(len(out) > 0)

    def test_mock_transcribe_returns_typed_text(self):
        p = MockAudioPipeline()
        out = p.record()
        Path(out).write_text("typed text", encoding="utf-8")
        self.assertEqual(p.transcribe(out), "typed text")

    def test_mock_speak_completes(self):
        p = MockAudioPipeline()
        self.assertIsNone(p.speak("hello"))

    @unittest.skipIf(AudioRecorder is None, "pyaudio not installed")
    def test_stereo_to_mono_wav_averages_channels(self):
        left = [1000, -3000, 2000]
        right = [3000, 1000, -2000]
        interleaved = []
        for lch, rch in zip(left, right):
            interleaved.extend([lch, rch])

        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "stereo.wav"
            dst = Path(tmpdir) / "mono.wav"

            with wave.open(str(src), "wb") as wav:
                wav.setnchannels(2)
                wav.setsampwidth(2)
                wav.setframerate(48000)
                wav.writeframes(struct.pack("<" + "h" * len(interleaved), *interleaved))

            AudioRecorder().stereo_to_mono_wav(str(src), str(dst))

            with wave.open(str(dst), "rb") as wav:
                self.assertEqual(wav.getnchannels(), 1)
                raw = wav.readframes(wav.getnframes())
                out = list(struct.unpack("<" + "h" * wav.getnframes(), raw))

        expected = [int((lch + rch) / 2.0) for lch, rch in zip(left, right)]
        self.assertEqual(out, expected)


if __name__ == "__main__":
    unittest.main()
