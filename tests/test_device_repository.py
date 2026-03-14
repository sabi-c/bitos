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


if __name__ == "__main__":
    unittest.main()
