import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from voice_catalog import build_catalog


class VoiceCatalogTests(unittest.TestCase):
    def test_catalog_has_engines(self):
        catalog = build_catalog()
        self.assertIn("engines", catalog)
        self.assertIn("current", catalog)

    def test_edge_tts_voices_listed(self):
        catalog = build_catalog()
        edge = catalog["engines"].get("edge_tts", {})
        self.assertGreater(len(edge.get("voices", [])), 0)
        # Each voice has id, name, gender
        v = edge["voices"][0]
        self.assertIn("id", v)
        self.assertIn("name", v)

    def test_engine_has_params(self):
        catalog = build_catalog()
        edge = catalog["engines"].get("edge_tts", {})
        self.assertIn("params", edge)
        self.assertIn("rate", edge["params"])

    def test_openai_voices_listed(self):
        catalog = build_catalog()
        oai = catalog["engines"].get("openai", {})
        ids = [v["id"] for v in oai.get("voices", [])]
        self.assertIn("alloy", ids)
        self.assertIn("nova", ids)

    def test_current_defaults(self):
        catalog = build_catalog()
        current = catalog["current"]
        self.assertIn("engine", current)
        self.assertIn("voice_id", current)


if __name__ == "__main__":
    unittest.main()
