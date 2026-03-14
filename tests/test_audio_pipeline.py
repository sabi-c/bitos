import os
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from audio.pipeline import AudioPipeline


class AudioPipelineTests(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("BITOS_AUDIO")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("BITOS_AUDIO", None)
        else:
            os.environ["BITOS_AUDIO"] = self._prev

    def test_mock_mode_is_noop_and_unavailable(self):
        os.environ["BITOS_AUDIO"] = "mock"
        pipeline = AudioPipeline()

        self.assertFalse(pipeline.is_available())
        self.assertEqual(pipeline.record(max_seconds=2.0), "")
        self.assertEqual(pipeline.transcribe("/tmp/fake.wav"), "")
        self.assertIsNone(pipeline.speak("hello"))

    def test_hw_mode_marks_available_and_raises_for_unimplemented_methods(self):
        os.environ["BITOS_AUDIO"] = "hw:0"
        pipeline = AudioPipeline()

        self.assertTrue(pipeline.is_available())
        with self.assertRaises(NotImplementedError):
            pipeline.record()
        with self.assertRaises(NotImplementedError):
            pipeline.transcribe("/tmp/fake.wav")
        self.assertIsNone(pipeline.speak("hello"))

    def test_unknown_mode_falls_back_to_mock(self):
        os.environ["BITOS_AUDIO"] = "invalid"
        pipeline = AudioPipeline()

        self.assertFalse(pipeline.is_available())
        self.assertEqual(pipeline.record(), "")


if __name__ == "__main__":
    unittest.main()
