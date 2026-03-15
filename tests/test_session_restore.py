import os
import tempfile
import time
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


class SessionRestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_get_latest_session_returns_none_when_no_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            self.assertIsNone(repo.get_latest_session())

    def test_get_latest_session_returns_most_recent_with_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            s1 = repo.create_session("old")
            repo.add_message(s1, "user", "a")
            time.sleep(0.01)
            s2 = repo.create_session("new")
            repo.add_message(s2, "user", "b")
            latest = repo.get_latest_session()
            self.assertEqual(int(latest["id"]), s2)

    def test_chat_panel_restores_session_on_init_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            s1 = repo.create_session("rest")
            repo.add_message(s1, "user", "hello")
            panel = ChatPanel(_NoopClient(), repository=repo)
            self.assertEqual(panel._session_id, s1)
            self.assertEqual(panel._messages[-1]["text"], "hello")

    def test_new_session_created_when_last_older_than_24_hours(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            s1 = repo.create_session("rest")
            repo.add_message(s1, "user", "hello")
            import sqlite3
            conn = sqlite3.connect(repo.db_path)
            conn.execute("UPDATE sessions SET created_at = created_at - ?", (25 * 3600,))
            conn.commit()
            conn.close()
            panel = ChatPanel(_NoopClient(), repository=repo)
            self.assertIsNone(panel._session_id)


if __name__ == "__main__":
    unittest.main()
