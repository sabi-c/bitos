import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.settings import AgentModePanel, ModelPickerPanel, SettingsPanel
from storage.repository import DeviceRepository


class SettingsWiringTests(unittest.TestCase):
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

    def test_toggle_reads_and_writes_repository(self):
        panel = SettingsPanel(repository=self.repo)
        self.assertTrue(self.repo.get_setting("web_search", default=True))
        self.assertTrue(self.repo.get_setting("memory", default=True))

        panel.handle_action("DOUBLE_PRESS")  # web_search toggle
        self.assertFalse(self.repo.get_setting("web_search", default=True))

        panel.handle_action("SHORT_PRESS")  # move to memory
        panel.handle_action("DOUBLE_PRESS")  # memory toggle
        self.assertFalse(self.repo.get_setting("memory", default=True))

    def test_model_picker_persists_selection(self):
        picker = ModelPickerPanel(repository=self.repo)

        picker.handle_action("SHORT_PRESS")  # opus
        picker.handle_action("DOUBLE_PRESS")

        self.assertEqual(self.repo.get_setting("ai_model", default="claude-sonnet-4-6"), "claude-opus-4-6")

    def test_agent_mode_picker_persists_selection(self):
        panel = AgentModePanel(repository=self.repo)

        panel.handle_action("SHORT_PRESS")  # clown
        panel.handle_action("SHORT_PRESS")  # monk
        panel.handle_action("DOUBLE_PRESS")

        self.assertEqual(self.repo.get_setting("agent_mode", default="producer"), "monk")


if __name__ == "__main__":
    unittest.main()
