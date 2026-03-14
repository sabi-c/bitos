import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from storage.repository import DeviceRepository
from overlays.quick_capture import QuickCaptureOverlay


class QuickCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_save_quick_capture_stores_and_retrieves(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            cap_id = repo.save_quick_capture("hello", context="CHAT")
            recent = repo.get_recent_captures(limit=1)
            self.assertEqual(recent[0]["id"], cap_id)
            self.assertEqual(recent[0]["text"], "hello")

    def test_get_recent_captures_returns_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            repo.save_quick_capture("first")
            repo.save_quick_capture("second")
            recent = repo.get_recent_captures(limit=2)
            self.assertEqual(recent[0]["text"], "second")

    def test_triple_press_triggers_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            overlay = QuickCaptureOverlay(repository=repo)
            self.assertEqual(overlay._mode, "keyboard")
            overlay.handle_input("TRIPLE_PRESS")
            self.assertEqual(overlay._mode, "voice")

    def test_capture_saved_on_confirm(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            overlay = QuickCaptureOverlay(repository=repo)
            event = pygame.event.Event(pygame.KEYDOWN, {"unicode": "x", "key": pygame.K_x})
            overlay.handle_keyboard_input(event)
            overlay.handle_input("LONG_PRESS")
            self.assertEqual(len(repo.get_recent_captures()), 1)

    def test_no_capture_saved_on_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            overlay = QuickCaptureOverlay(repository=repo)
            overlay.handle_input("DOUBLE_PRESS")
            self.assertEqual(len(repo.get_recent_captures()), 0)


if __name__ == "__main__":
    unittest.main()
