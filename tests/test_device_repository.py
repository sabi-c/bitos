import tempfile
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from storage.repository import DeviceRepository, LATEST_SCHEMA_VERSION


class DeviceRepositoryTests(unittest.TestCase):
    def test_initialize_creates_schema_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            self.assertEqual(repo.get_schema_version(), LATEST_SCHEMA_VERSION)


    def test_initialize_migrates_v1_database_to_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "bitos.db"
            import sqlite3

            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
            conn.execute("INSERT INTO schema_version(version) VALUES (1)")
            conn.execute("""
                CREATE TABLE sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.commit()
            conn.close()

            repo = DeviceRepository(db_path=str(db_path))
            repo.initialize()

            self.assertEqual(repo.get_schema_version(), LATEST_SCHEMA_VERSION)

            conn = sqlite3.connect(db_path)
            outbound_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='outbound_commands'"
            ).fetchone()
            notif_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
            ).fetchone()
            cols = conn.execute("PRAGMA table_info(tasks)").fetchall()
            conn.close()
            self.assertIsNotNone(outbound_row)
            self.assertIsNotNone(notif_row)
            self.assertIn("due_date", {c[1] for c in cols})

    def test_migration_guard_adds_due_date_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "bitos.db"
            import sqlite3

            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
            conn.execute("INSERT INTO schema_version(version) VALUES (2)")
            conn.execute("""
                CREATE TABLE sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.commit()
            conn.close()

            repo = DeviceRepository(db_path=str(db_path))
            repo.initialize()

            conn = sqlite3.connect(db_path)
            cols = conn.execute("PRAGMA table_info(tasks)").fetchall()
            conn.close()
            self.assertIn("due_date", {c[1] for c in cols})


    def test_session_and_message_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()

            session_id = repo.create_session("hello")
            repo.add_message(session_id, "user", "hey")
            repo.add_message(session_id, "assistant", "yo")

            latest, messages = repo.load_latest_session_messages()
            self.assertEqual(latest, session_id)
            self.assertEqual([m["role"] for m in messages], ["user", "assistant"])
            self.assertEqual([m["text"] for m in messages], ["hey", "yo"])


class GreetingSessionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "bitos.db")
        self.repo = DeviceRepository(db_path=self.db_path)
        self.repo.initialize()

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_greeting_session(self):
        sid = self.repo.create_greeting_session("good morning")
        self.assertIsNotNone(sid)
        msgs = self.repo.list_messages(sid)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "assistant")
        self.assertEqual(msgs[0]["text"], "good morning")

    def test_get_greeting_session_returns_recent(self):
        sid = self.repo.create_greeting_session("hello there")
        result = self.repo.get_greeting_session()
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], sid)

    def test_get_greeting_session_returns_none_when_empty(self):
        result = self.repo.get_greeting_session()
        self.assertIsNone(result)

    def test_get_latest_chat_session_excludes_greeting(self):
        self.repo.create_greeting_session("hi there")
        chat_id = self.repo.create_session(title="real chat")
        self.repo.add_message(chat_id, "user", "hello")
        result = self.repo.get_latest_chat_session()
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], chat_id)

    def test_get_latest_chat_session_returns_none_when_only_greeting(self):
        self.repo.create_greeting_session("hi")
        result = self.repo.get_latest_chat_session()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
