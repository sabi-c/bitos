import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "device"))
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "integrations"))

from fastapi.testclient import TestClient
import main as server_main
from vikunja_adapter import VikunjaAdapter
from screens.panels.tasks import TasksPanel


class _Client:
    async def get_tasks(self):
        return [{"id": 1, "title": "Task one", "project": "P"}]


class _Repo:
    def __init__(self):
        self.cached = []

    def cache_today_tasks(self, tasks):
        self.cached = tasks

    def get_cached_today_tasks(self):
        return self.cached


class TasksPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_tasks_today_returns_list_from_adapter(self):
        client = TestClient(server_main.app)
        resp = client.get("/tasks/today")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("tasks", resp.json())

    def test_mock_mode_returns_three_demo_tasks(self):
        adapter = VikunjaAdapter(api_token="")
        tasks = adapter.get_today_tasks()
        self.assertEqual(len(tasks), 3)

    def test_tasks_panel_renders_task_list(self):
        panel = TasksPanel(client=_Client(), repository=_Repo())
        panel._tasks = [{"id": 1, "title": "Ship", "project": "BITOS"}]
        panel._state = "ready"
        surface = pygame.Surface((240, 280))
        panel.render(surface)
        self.assertEqual(panel._tasks[0]["title"], "Ship")

    def test_empty_state_renders_correctly(self):
        panel = TasksPanel(client=_Client(), repository=_Repo())
        panel._tasks = []
        panel._state = "empty"
        surface = pygame.Surface((240, 280))
        panel.render(surface)
        self.assertEqual(panel._state, "empty")


if __name__ == "__main__":
    unittest.main()
