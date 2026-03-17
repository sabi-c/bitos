"""Tests for server/voice_catalog.py — catalog building, engine availability checks."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from voice_catalog import build_catalog, _check_edge_tts, _check_cartesia


class TestBuildCatalog(unittest.TestCase):
    """Test the voice catalog builder returns correct structure."""

    def test_returns_engines_and_current(self):
        catalog = build_catalog()
        self.assertIn("engines", catalog)
        self.assertIn("current", catalog)

    def test_all_engines_present(self):
        catalog = build_catalog()
        expected = {"edge_tts", "cartesia", "speechify", "openai", "espeak"}
        self.assertEqual(set(catalog["engines"].keys()), expected)

    def test_each_engine_has_required_fields(self):
        catalog = build_catalog()
        for name, engine in catalog["engines"].items():
            self.assertIn("available", engine, f"{name} missing 'available'")
            self.assertIn("requires_key", engine, f"{name} missing 'requires_key'")
            self.assertIn("voices", engine, f"{name} missing 'voices'")
            self.assertIn("params", engine, f"{name} missing 'params'")
            self.assertIsInstance(engine["voices"], list, f"{name} voices not a list")
            self.assertTrue(len(engine["voices"]) > 0, f"{name} has no voices")

    def test_voice_entries_have_id_and_name(self):
        catalog = build_catalog()
        for name, engine in catalog["engines"].items():
            for voice in engine["voices"]:
                self.assertIn("id", voice, f"{name} voice missing 'id'")
                self.assertIn("name", voice, f"{name} voice missing 'name'")
                self.assertIn("gender", voice, f"{name} voice missing 'gender'")

    def test_current_reflects_arguments(self):
        catalog = build_catalog(
            current_engine="speechify",
            current_voice_id="henry",
            current_params={"model": "simba-turbo"},
        )
        self.assertEqual(catalog["current"]["engine"], "speechify")
        self.assertEqual(catalog["current"]["voice_id"], "henry")
        self.assertEqual(catalog["current"]["params"]["model"], "simba-turbo")

    def test_current_defaults_empty(self):
        catalog = build_catalog()
        self.assertEqual(catalog["current"]["engine"], "auto")
        self.assertEqual(catalog["current"]["voice_id"], "")
        self.assertEqual(catalog["current"]["params"], {})

    def test_edge_tts_no_key_required(self):
        catalog = build_catalog()
        self.assertFalse(catalog["engines"]["edge_tts"]["requires_key"])

    def test_cartesia_requires_key(self):
        catalog = build_catalog()
        self.assertTrue(catalog["engines"]["cartesia"]["requires_key"])

    def test_openai_requires_key(self):
        catalog = build_catalog()
        self.assertTrue(catalog["engines"]["openai"]["requires_key"])

    def test_espeak_no_key_required(self):
        catalog = build_catalog()
        self.assertFalse(catalog["engines"]["espeak"]["requires_key"])

    def test_edge_tts_has_rate_and_pitch_params(self):
        catalog = build_catalog()
        params = catalog["engines"]["edge_tts"]["params"]
        self.assertIn("rate", params)
        self.assertIn("pitch", params)

    def test_openai_has_speed_slider(self):
        catalog = build_catalog()
        params = catalog["engines"]["openai"]["params"]
        self.assertIn("speed", params)
        self.assertEqual(params["speed"]["type"], "slider")

    def test_openai_voices_listed(self):
        catalog = build_catalog()
        oai = catalog["engines"]["openai"]
        ids = [v["id"] for v in oai["voices"]]
        self.assertIn("alloy", ids)
        self.assertIn("nova", ids)

    def test_espeak_has_speed_and_pitch(self):
        catalog = build_catalog()
        params = catalog["engines"]["espeak"]["params"]
        self.assertIn("speed", params)
        self.assertIn("pitch", params)

    def test_speechify_has_model_param(self):
        catalog = build_catalog()
        params = catalog["engines"]["speechify"]["params"]
        self.assertIn("model", params)
        self.assertEqual(params["model"]["type"], "choice")


class TestEngineAvailability(unittest.TestCase):
    """Test engine availability checks."""

    @patch.dict(os.environ, {"CARTESIA_API_KEY": ""}, clear=False)
    def test_cartesia_unavailable_without_key(self):
        self.assertFalse(_check_cartesia())

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False)
    def test_openai_available_with_key(self):
        catalog = build_catalog()
        self.assertTrue(catalog["engines"]["openai"]["available"])

    @patch.dict(os.environ, {}, clear=True)
    def test_openai_unavailable_without_key(self):
        catalog = build_catalog()
        self.assertFalse(catalog["engines"]["openai"]["available"])

    @patch.dict(os.environ, {}, clear=True)
    def test_speechify_unavailable_without_key(self):
        catalog = build_catalog()
        self.assertFalse(catalog["engines"]["speechify"]["available"])

    @patch.dict(os.environ, {"SPEECHIFY_API_KEY": "sp-test"}, clear=False)
    def test_speechify_available_with_key(self):
        catalog = build_catalog()
        self.assertTrue(catalog["engines"]["speechify"]["available"])


if __name__ == "__main__":
    unittest.main()
