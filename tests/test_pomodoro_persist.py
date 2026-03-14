import json
import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.focus import FocusPanel
from storage.repository import DeviceRepository


class PomodoroPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_save_state_writes_repository_when_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            panel = FocusPanel(duration_seconds=300, repository=repo)
            panel._running = True
            panel._elapsed_seconds = 42
            panel._total_seconds = 300

            panel.save_state()

            raw = repo.get_setting("pomodoro_state", None)
            self.assertIsNotNone(raw)
            state = json.loads(raw)
            self.assertTrue(state["running"])
            self.assertEqual(state["elapsed_s"], 42)
            self.assertEqual(state["total_s"], 300)

    def test_save_state_does_nothing_when_not_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            panel = FocusPanel(duration_seconds=300, repository=repo)
            panel._running = False

            panel.save_state()

            self.assertIsNone(repo.get_setting("pomodoro_state", None))

    def test_restore_state_sets_running_true_for_fresh_state(self):
        panel = FocusPanel(duration_seconds=300)
        panel.restore_state(
            {
                "running": True,
                "elapsed_s": 30,
                "total_s": 300,
                "saved_at": time.time() - 3,
            }
        )

        self.assertTrue(panel._running)
        self.assertGreaterEqual(panel._elapsed_seconds, 33)
        self.assertEqual(panel._total_seconds, 300)

    def test_restore_state_ignores_stale_state(self):
        panel = FocusPanel(duration_seconds=300)
        panel.restore_state(
            {
                "running": True,
                "elapsed_s": 30,
                "total_s": 300,
                "saved_at": time.time() - 4000,
            }
        )

        self.assertFalse(panel._running)
        self.assertEqual(panel._elapsed_seconds, 0)


if __name__ == "__main__":
    unittest.main()
