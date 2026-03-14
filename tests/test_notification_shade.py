import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from overlays.notification import NotificationQueue, NotificationRecord, NotificationShade
from storage.repository import DeviceRepository


class NotificationShadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _queue_with_repo(self):
        tmp = tempfile.TemporaryDirectory()
        repo = DeviceRepository(db_path=str(Path(tmp.name) / "bitos.db"))
        repo.initialize()
        return tmp, repo, NotificationQueue(repository=repo)

    def test_shade_renders_records(self):
        tmp, _repo, queue = self._queue_with_repo()
        try:
            for i in range(3):
                queue.push_record(
                    NotificationRecord(
                        id=f"n-{i}",
                        type="CLAUDE",
                        app_name="CLAUDE",
                        message=f"msg-{i}",
                        time_str="10:1",
                    )
                )
            shade = NotificationShade(queue=queue)
            surface = pygame.Surface((240, 280))
            shade.render(surface, __import__("display.tokens", fromlist=["*"]))
            self.assertGreater(surface.get_at((5, 6))[0], 0)
        finally:
            tmp.cleanup()

    def test_short_press_cycles_cursor(self):
        tmp, _repo, queue = self._queue_with_repo()
        try:
            queue.push_record(NotificationRecord(id="1", type="SMS", app_name="SMS", message="a", time_str="09:00"))
            queue.push_record(NotificationRecord(id="2", type="MAIL", app_name="MAIL", message="b", time_str="09:01"))
            shade = NotificationShade(queue=queue)
            shade.handle_input("SHORT_PRESS")
            self.assertTrue(shade.handle_input("SHORT_PRESS"))
        finally:
            tmp.cleanup()

    def test_long_press_marks_read_and_fires_callback(self):
        tmp, _repo, queue = self._queue_with_repo()
        called = {"source": None}
        try:
            queue.push_record(
                NotificationRecord(
                    id="note-1",
                    type="TASK",
                    app_name="TASKS",
                    message="File taxes",
                    time_str="08:00",
                    source_id="task-1",
                )
            )
            shade = NotificationShade(queue=queue, on_open_source=lambda source: called.__setitem__("source", source))
            consumed = shade.handle_input("LONG_PRESS")
            self.assertTrue(consumed)
            self.assertEqual(called["source"], "task-1")
            rec = queue.get_all()[0]
            self.assertTrue(rec.read)
        finally:
            tmp.cleanup()

    def test_double_press_closes_shade(self):
        tmp, _repo, queue = self._queue_with_repo()
        closed = {"called": False}
        try:
            shade = NotificationShade(queue=queue, on_close=lambda: closed.__setitem__("called", True))
            consumed = shade.handle_input("DOUBLE_PRESS")
            self.assertTrue(consumed)
            self.assertTrue(closed["called"])
        finally:
            tmp.cleanup()

    def test_empty_state_renders(self):
        tmp, _repo, queue = self._queue_with_repo()
        try:
            shade = NotificationShade(queue=queue)
            surface = pygame.Surface((240, 280))
            shade.render(surface, __import__("display.tokens", fromlist=["*"]))
            self.assertEqual(queue.get_all(), [])
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
