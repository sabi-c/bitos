"""Tests for RecordingStore CRUD operations."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from device.recordings import RecordingStore, Recording


class RecordingModelTests(unittest.TestCase):
    def test_to_dict_roundtrip(self):
        rec = Recording(id="rec_123", recorded_at="2026-03-16T10:00:00+00:00",
                        duration_s=45.0, tags=["nature"])
        d = rec.to_dict()
        restored = Recording.from_dict(d)
        self.assertEqual(restored.id, "rec_123")
        self.assertEqual(restored.duration_s, 45.0)
        self.assertEqual(restored.tags, ["nature"])

    def test_from_dict_ignores_extra_keys(self):
        d = {"id": "rec_1", "recorded_at": "2026-01-01T00:00:00+00:00",
             "unknown_field": True}
        rec = Recording.from_dict(d)
        self.assertEqual(rec.id, "rec_1")

    def test_defaults(self):
        rec = Recording(id="rec_1", recorded_at="2026-01-01T00:00:00+00:00")
        self.assertEqual(rec.status, "recorded")
        self.assertEqual(rec.sync_status, "local_only")
        self.assertEqual(rec.bookmarks, [])
        self.assertEqual(rec.tags, [])
        self.assertIsNone(rec.summary)


class RecordingStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._json_path = os.path.join(self._tmpdir, "recordings.json")
        self.store = RecordingStore(path=self._json_path)

    def tearDown(self):
        if os.path.exists(self._json_path):
            os.remove(self._json_path)
        os.rmdir(self._tmpdir)

    def test_create_and_get(self):
        rec = self.store.create(duration_s=30.5)
        self.assertTrue(rec.id.startswith("rec_"))
        self.assertEqual(rec.duration_s, 30.5)

        fetched = self.store.get(rec.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, rec.id)
        self.assertEqual(fetched.duration_s, 30.5)

    def test_get_nonexistent_returns_none(self):
        self.assertIsNone(self.store.get("rec_doesnotexist"))

    def test_list_recent_ordering(self):
        r1 = self.store.create(duration_s=10.0)
        r2 = self.store.create(duration_s=20.0)
        recent = self.store.list_recent(limit=10)
        # Most recent first
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0].id, r2.id)

    def test_list_recent_limit(self):
        for _ in range(5):
            self.store.create(duration_s=1.0)
        recent = self.store.list_recent(limit=3)
        self.assertEqual(len(recent), 3)

    def test_update(self):
        rec = self.store.create(duration_s=60.0)
        updated = self.store.update(rec.id, status="complete", tags=["interview"])
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, "complete")
        self.assertEqual(updated.tags, ["interview"])

        # Persisted
        fetched = self.store.get(rec.id)
        self.assertEqual(fetched.status, "complete")

    def test_update_nonexistent_returns_none(self):
        self.assertIsNone(self.store.update("nope", status="x"))

    def test_update_cannot_change_id(self):
        rec = self.store.create(duration_s=1.0)
        updated = self.store.update(rec.id, id="hacked")
        self.assertEqual(updated.id, rec.id)

    def test_delete(self):
        rec = self.store.create(duration_s=5.0)
        self.assertTrue(self.store.delete(rec.id))
        self.assertIsNone(self.store.get(rec.id))
        self.assertEqual(self.store.count(), 0)

    def test_delete_nonexistent_returns_false(self):
        self.assertFalse(self.store.delete("nope"))

    def test_count(self):
        self.assertEqual(self.store.count(), 0)
        self.store.create(duration_s=1.0)
        self.store.create(duration_s=2.0)
        self.assertEqual(self.store.count(), 2)

    def test_empty_file_handled(self):
        # Write empty file
        with open(self._json_path, "w") as f:
            f.write("")
        self.assertEqual(self.store.list_recent(), [])

    def test_corrupt_json_handled(self):
        with open(self._json_path, "w") as f:
            f.write("{{{bad json")
        self.assertEqual(self.store.list_recent(), [])

    def test_json_file_created_on_first_write(self):
        os.remove(self._json_path) if os.path.exists(self._json_path) else None
        self.store.create(duration_s=1.0)
        self.assertTrue(os.path.exists(self._json_path))
        with open(self._json_path, "r") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)


if __name__ == "__main__":
    unittest.main()
