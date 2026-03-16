"""Tests for the AgentTasksPanel and related backend endpoints."""
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
from fastapi.testclient import TestClient

import main as server_main
from screens.panels.agent_tasks import AgentTasksPanel


class _MockClient:
    """Mock backend client returning canned subtask data."""

    def __init__(self, subtasks=None):
        self._subtasks = subtasks if subtasks is not None else []

    def get_agent_subtasks(self, status=None):
        if status:
            return [t for t in self._subtasks if t.get("status") == status]
        return self._subtasks


class _MockRepo:
    pass


_SAMPLE_TASKS = [
    {"id": "abc123", "name": "markdown-parse", "status": "complete", "cost_usd": 0.002, "result": "Some result text here."},
    {"id": "def456", "name": "summarize", "status": "running", "cost_usd": 0.0, "result": None},
    {"id": "ghi789", "name": "translate", "status": "failed", "cost_usd": 0.0, "error": "Timeout"},
]


class AgentTasksPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_panel(self, tasks=None):
        client = _MockClient(tasks or _SAMPLE_TASKS)
        return AgentTasksPanel(client=client, repository=_MockRepo())

    def test_creation_and_initial_state(self):
        panel = self._make_panel()
        self.assertEqual(panel._state, "loading")
        self.assertEqual(panel._cursor, 0)
        self.assertFalse(panel._expanded)

    def test_renders_task_list(self):
        panel = self._make_panel()
        panel._tasks = _SAMPLE_TASKS
        panel._state = "ready"
        surface = pygame.Surface((240, 280))
        panel.render(surface)
        self.assertEqual(len(panel._tasks), 3)

    def test_empty_state_renders(self):
        panel = self._make_panel(tasks=[])
        panel._tasks = []
        panel._state = "empty"
        surface = pygame.Surface((240, 280))
        panel.render(surface)
        self.assertEqual(panel._state, "empty")

    def test_short_press_scrolls_cursor(self):
        panel = self._make_panel()
        panel._tasks = _SAMPLE_TASKS
        panel._state = "ready"
        self.assertEqual(panel._cursor, 0)
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._cursor, 1)
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._cursor, 2)
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._cursor, 0)  # wraps around

    def test_triple_press_scrolls_backward(self):
        panel = self._make_panel()
        panel._tasks = _SAMPLE_TASKS
        panel._state = "ready"
        panel.handle_action("TRIPLE_PRESS")
        self.assertEqual(panel._cursor, 2)  # wraps to end

    def test_double_press_expands_task(self):
        panel = self._make_panel()
        panel._tasks = _SAMPLE_TASKS
        panel._state = "ready"
        panel.handle_action("DOUBLE_PRESS")
        self.assertTrue(panel._expanded)
        self.assertTrue(len(panel._detail_pages) >= 1)

    def test_long_press_exits_expanded(self):
        panel = self._make_panel()
        panel._tasks = _SAMPLE_TASKS
        panel._state = "ready"
        panel.handle_action("DOUBLE_PRESS")
        self.assertTrue(panel._expanded)
        panel.handle_action("LONG_PRESS")
        self.assertFalse(panel._expanded)

    def test_long_press_calls_on_back(self):
        called = []
        panel = self._make_panel()
        panel._on_back = lambda: called.append(True)
        panel._tasks = _SAMPLE_TASKS
        panel._state = "ready"
        panel.handle_action("LONG_PRESS")
        self.assertEqual(len(called), 1)

    def test_action_bar_list_view(self):
        panel = self._make_panel()
        panel._tasks = _SAMPLE_TASKS
        panel._state = "ready"
        bar = panel.get_action_bar()
        labels = [label for _, label in bar]
        self.assertIn("scroll", labels)
        self.assertIn("expand", labels)
        self.assertIn("back", labels)

    def test_action_bar_expanded_view(self):
        panel = self._make_panel()
        panel._tasks = _SAMPLE_TASKS
        panel._state = "ready"
        panel.handle_action("DOUBLE_PRESS")
        bar = panel.get_action_bar()
        labels = [label for _, label in bar]
        self.assertIn("page", labels)
        self.assertIn("back", labels)

    def test_action_bar_empty_state(self):
        panel = self._make_panel(tasks=[])
        panel._tasks = []
        panel._state = "empty"
        bar = panel.get_action_bar()
        labels = [label for _, label in bar]
        self.assertIn("back", labels)
        self.assertNotIn("scroll", labels)

    def test_expanded_render(self):
        panel = self._make_panel()
        panel._tasks = _SAMPLE_TASKS
        panel._state = "ready"
        panel.handle_action("DOUBLE_PRESS")
        surface = pygame.Surface((240, 280))
        panel.render(surface)
        # Should render without error in expanded mode
        self.assertTrue(panel._expanded)


class AgentSubtaskServerTests(unittest.TestCase):
    def test_list_subtasks_endpoint(self):
        client = TestClient(server_main.app)
        resp = client.get("/agent/subtasks")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("subtasks", resp.json())

    def test_create_subtask_endpoint(self):
        client = TestClient(server_main.app)
        resp = client.post("/agent/subtasks", json={"name": "test-task", "prompt": "Say hello"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("task_id", data)
        self.assertEqual(data["status"], "pending")

    def test_get_subtask_not_found(self):
        client = TestClient(server_main.app)
        resp = client.get("/agent/subtasks/nonexistent")
        self.assertEqual(resp.status_code, 404)

    def test_create_test_subtask_endpoint(self):
        client = TestClient(server_main.app)
        resp = client.post("/agent/subtasks/test")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("task_id", data)
        self.assertEqual(data["name"], "markdown-parse")


if __name__ == "__main__":
    unittest.main()
