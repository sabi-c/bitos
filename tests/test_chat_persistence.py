import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.chat import ChatPanel
from storage.repository import DeviceRepository


class _NoopClient:
    def chat(self, _message):
        return iter(())


class ChatPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_chat_panel_hydrates_latest_session_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()

            session_id = repo.create_session("Restored")
            repo.add_message(session_id, "user", "restored user")
            repo.add_message(session_id, "assistant", "restored assistant")

            panel = ChatPanel(_NoopClient(), repository=repo)
            self.assertEqual(len(panel._messages), 2)
            self.assertEqual(panel._messages[0]["text"], "restored user")
            self.assertEqual(panel._messages[1]["text"], "restored assistant")


if __name__ == "__main__":
    unittest.main()
