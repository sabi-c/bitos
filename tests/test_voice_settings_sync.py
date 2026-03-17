"""Test that voice settings flow through the system correctly."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from storage.repository import DeviceRepository
from voice_catalog import build_catalog


class VoiceSettingsSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = DeviceRepository(db_path=str(Path(self.tmp.name) / "bitos.db"))
        self.repo.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def test_voice_id_persists(self):
        self.repo.set_setting("voice_id", "en-US-GuyNeural")
        self.assertEqual(self.repo.get_setting("voice_id"), "en-US-GuyNeural")

    def test_voice_params_persists_json(self):
        params = {"rate": "+10%", "pitch": "-5Hz"}
        self.repo.set_setting("voice_params", json.dumps(params))
        stored = json.loads(self.repo.get_setting("voice_params"))
        self.assertEqual(stored["rate"], "+10%")

    def test_typewriter_config_persists(self):
        config = {"base_speed_ms": 60, "jitter_amount": 0.05}
        self.repo.set_setting("typewriter_config", json.dumps(config))
        stored = json.loads(self.repo.get_setting("typewriter_config"))
        self.assertEqual(stored["base_speed_ms"], 60)

    def test_catalog_reflects_current_settings(self):
        catalog = build_catalog(
            current_engine="edge_tts",
            current_voice_id="en-US-GuyNeural",
            current_params={"rate": "+10%"},
        )
        self.assertEqual(catalog["current"]["engine"], "edge_tts")
        self.assertEqual(catalog["current"]["voice_id"], "en-US-GuyNeural")
        self.assertEqual(catalog["current"]["params"]["rate"], "+10%")

    def test_setting_validators_accept_voice_id(self):
        from agent_tools import validate_setting
        ok, err, val = validate_setting("voice_id", "en-US-AriaNeural")
        self.assertTrue(ok)
        self.assertEqual(val, "en-US-AriaNeural")

    def test_setting_validators_accept_voice_params_json(self):
        from agent_tools import validate_setting
        ok, err, val = validate_setting("voice_params", '{"rate": "+10%"}')
        self.assertTrue(ok)

    def test_setting_validators_accept_typewriter_config(self):
        from agent_tools import validate_setting
        config = json.dumps({"base_speed_ms": 50})
        ok, err, val = validate_setting("typewriter_config", config)
        self.assertTrue(ok)

    def test_setting_validators_reject_bad_json(self):
        from agent_tools import validate_setting
        ok, err, val = validate_setting("voice_params", "not json")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
