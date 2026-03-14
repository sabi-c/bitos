import os
import tempfile
import unittest
from pathlib import Path
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.settings import SettingsPanel
from storage.repository import DeviceRepository


class SettingsCompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = DeviceRepository(db_path=str(Path(self.tmp.name) / "bitos.db"))
        self.repo.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def test_companion_row_reachable_via_short_presses(self):
        panel = SettingsPanel(repository=self.repo)
        for _ in range(6):
            panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel._nav.focused_item.key, "companion")

    def test_long_press_companion_invokes_get_ble_address(self):
        calls = {"ble": 0}

        def get_ble_address():
            calls["ble"] += 1
            return "AA:BB"

        panel = SettingsPanel(repository=self.repo, get_ble_address=get_ble_address)
        for _ in range(6):
            panel.handle_action("DOUBLE_PRESS")
        panel.handle_action("LONG_PRESS")
        self.assertEqual(calls["ble"], 1)


if __name__ == "__main__":
    unittest.main()
