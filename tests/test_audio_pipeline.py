import os
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from audio.pipeline import AudioPipeline, MockAudioPipeline, WM8960Pipeline, get_audio_pipeline


class AudioPipelineTests(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("BITOS_AUDIO")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("BITOS_AUDIO", None)
        else:
            os.environ["BITOS_AUDIO"] = self._prev

    def test_audio_pipeline_base_is_unavailable(self):
        self.assertFalse(AudioPipeline().is_available())

    def test_factory_uses_hw_for_generic_hw_mode(self):
        os.environ["BITOS_AUDIO"] = "hw:1"
        self.assertIsInstance(get_audio_pipeline(), WM8960Pipeline)

    def test_factory_falls_back_to_mock_for_unknown_mode(self):
        os.environ["BITOS_AUDIO"] = "invalid"
        self.assertIsInstance(get_audio_pipeline(), MockAudioPipeline)


if __name__ == "__main__":
    unittest.main()
