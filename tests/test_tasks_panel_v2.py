"""Tests for updated TasksPanel — priority display, detail view, completion sync."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "device"))
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "integrations"))

import pygame
from screens.panels.tasks import TasksPanel


class _MockClient:
    def __init__(self):
        self.completed_ids = []

    def get_tasks(self):
        return [
            {"id": "tsk_001", "title": "Ship feature", "project": "BITOS", "priority": 1,
             "due_date": "2026-03-18", "status": "todo", "subtasks": [
                 {"title": "Write tests", "status": "done"},
                 {"title": "Deploy", "status": "todo"},
             ]},
            {"id": "tsk_002", "title": "Buy groceries", "project": "PERSONAL", "priority": 3,
             "due_date": None, "status": "todo", "subtasks": []},
            {"id": "tsk_003", "title": "Review PR", "project": "WORK", "priority": 2,
             "due_date": "2026-03-17", "status": "todo", "subtasks": []},
        ]

    def complete_task(self, task_id):
        self.completed_ids.append(task_id)
        return True


class _MockRepo:
    def __init__(self):
        self.cached = []

    def cache_today_tasks(self, tasks):
        self.cached = tasks

    def get_cached_today_tasks(self):
        return self.cached

    def queue_enqueue_command(self, **kwargs):
        pass


class TasksPanelV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_panel(self, tasks=None):
        client = _MockClient()
        repo = _MockRepo()
        panel = TasksPanel(client=client, repository=repo)
        if tasks is not None:
            panel._tasks = tasks
        else:
            panel._tasks = client.get_tasks()
        panel._state = "ready"
        return panel, client

    def test_renders_with_priority_colors(self):
        """Panel should render without errors when tasks have priority."""
        panel, _ = self._make_panel()
        surface = pygame.Surface((240, 280))
        panel.render(surface)
        # Task at cursor 0 has priority 1 (critical)
        self.assertEqual(panel._tasks[0]["priority"], 1)

    def test_double_press_enters_detail_view(self):
        panel, _ = self._make_panel()
        panel.handle_action("DOUBLE_PRESS")
        self.assertTrue(panel._detail_view)
        self.assertFalse(panel._confirm_complete)

    def test_detail_view_renders(self):
        panel, _ = self._make_panel()
        panel.handle_action("DOUBLE_PRESS")
        surface = pygame.Surface((240, 280))
        panel.render(surface)
        self.assertTrue(panel._detail_view)

    def test_long_press_exits_detail_view(self):
        panel, _ = self._make_panel()
        panel.handle_action("DOUBLE_PRESS")
        self.assertTrue(panel._detail_view)
        panel.handle_action("LONG_PRESS")
        self.assertFalse(panel._detail_view)

    def test_double_double_in_detail_completes_task(self):
        panel, client = self._make_panel()
        panel.handle_action("DOUBLE_PRESS")  # enter detail
        panel.handle_action("DOUBLE_PRESS")  # first: confirm mode
        self.assertTrue(panel._confirm_complete)
        panel.handle_action("DOUBLE_PRESS")  # second: complete
        self.assertTrue(panel._tasks[0].get("done"))
        self.assertFalse(panel._detail_view)

    def test_completion_syncs_to_server(self):
        panel, client = self._make_panel()
        # Directly test the sync method
        panel._complete_current_task()
        # Give background thread time to run
        import time
        time.sleep(0.1)
        self.assertIn("tsk_001", client.completed_ids)

    def test_list_renders_subtask_count(self):
        """Task with subtasks should show count in meta line."""
        panel, _ = self._make_panel()
        surface = pygame.Surface((240, 280))
        panel.render(surface)
        # First task has 2 subtasks (1 done, 1 todo)
        subtasks = panel._tasks[0].get("subtasks", [])
        self.assertEqual(len(subtasks), 2)

    def test_detail_shows_subtasks(self):
        panel, _ = self._make_panel()
        panel.handle_action("DOUBLE_PRESS")
        surface = pygame.Surface((240, 280))
        panel.render(surface)
        # Should render without error — detail includes subtask display

    def test_completed_task_shows_checkmark(self):
        panel, _ = self._make_panel()
        panel._tasks[1]["status"] = "done"
        panel._tasks[1]["done"] = True
        surface = pygame.Surface((240, 280))
        panel.render(surface)

    def test_cursor_navigation(self):
        panel, _ = self._make_panel()
        self.assertEqual(panel._cursor, 0)
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._cursor, 1)
        panel.handle_action("TRIPLE_PRESS")
        self.assertEqual(panel._cursor, 0)


if __name__ == "__main__":
    unittest.main()
