import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.notifications import NotificationsPanel
from screens.panels.settings import SettingsPanel
from storage.repository import DeviceRepository
import tempfile


class PanelShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_notifications_back_action_callback(self):
        calls = {"count": 0}

        def on_back():
            calls["count"] += 1

        panel = NotificationsPanel(on_back=on_back)
        panel.handle_action("DOUBLE_PRESS")  # DOUBLE_PRESS = back
        self.assertEqual(calls["count"], 1)

    def test_notifications_error_copy_setter(self):
        panel = NotificationsPanel()
        panel.set_error("network down")
        self.assertEqual(panel._error_copy, "network down")

    def test_settings_back_action_callback(self):
        calls = {"count": 0}

        def on_back():
            calls["count"] += 1

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DeviceRepository(db_path=str(Path(tmpdir) / "bitos.db"))
            repo.initialize()
            panel = SettingsPanel(repository=repo, on_back=on_back)
            panel.handle_action("DOUBLE_PRESS")  # DOUBLE_PRESS = back
            self.assertEqual(calls["count"], 1)


if __name__ == "__main__":
    unittest.main()
