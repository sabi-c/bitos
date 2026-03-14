import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from ui_settings import UISettingsStore, UISettingsValidationError


class UISettingsStoreTests(unittest.TestCase):
    def test_defaults_written_on_first_load(self):
        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "ui_settings.json"
            store = UISettingsStore(str(file_path))
            settings = store.get()
            self.assertEqual(settings["font_family"], "press_start_2p")
            self.assertTrue(file_path.exists())

    def test_update_valid_patch(self):
        with tempfile.TemporaryDirectory() as td:
            store = UISettingsStore(str(Path(td) / "ui_settings.json"))
            updated = store.update({"font_scale": 1.25, "layout_density": "compact"})
            self.assertEqual(updated["font_scale"], 1.25)
            self.assertEqual(updated["layout_density"], "compact")

    def test_update_invalid_patch_raises(self):
        with tempfile.TemporaryDirectory() as td:
            store = UISettingsStore(str(Path(td) / "ui_settings.json"))
            with self.assertRaises(UISettingsValidationError):
                store.update({"font_scale": 9.0})


if __name__ == "__main__":
    unittest.main()
