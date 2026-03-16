"""Tests for FilesBrowserPanel."""
import os
import sys
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "device"))
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "server" / "integrations"))

from screens.panels.files_browser import FilesBrowserPanel


class _MockClient:
    def __init__(self, files=None):
        self._files = files or []

    def get_files(self, path=""):
        return self._files


SAMPLE_FILES = [
    {"id": "abc", "name": "welcome", "path": "welcome.md", "size": 500, "type": "markdown"},
    {"id": "def", "name": "getting-started", "path": "getting-started.md", "size": 800, "type": "markdown"},
    {"id": "ghi", "name": "about", "path": "about.md", "size": 400, "type": "markdown"},
]


class FilesBrowserPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()

    def _make_panel(self, files=None, on_back=None, on_open_file=None):
        client = _MockClient(files=files or SAMPLE_FILES)
        panel = FilesBrowserPanel(
            client=client,
            on_back=on_back,
            on_open_file=on_open_file,
        )
        # Simulate loaded state
        panel._files = files if files is not None else list(SAMPLE_FILES)
        panel._state = "ready" if panel._files else "empty"
        return panel

    def test_creation(self):
        panel = self._make_panel()
        self.assertEqual(panel._state, "ready")
        self.assertEqual(len(panel._files), 3)
        self.assertEqual(panel._cursor, 0)

    def test_short_press_cycles_files(self):
        panel = self._make_panel()
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._cursor, 1)
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._cursor, 2)
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._cursor, 0)  # wraps

    def test_triple_press_cycles_backward(self):
        panel = self._make_panel()
        panel.handle_action("TRIPLE_PRESS")
        self.assertEqual(panel._cursor, 2)  # wraps backward
        panel.handle_action("TRIPLE_PRESS")
        self.assertEqual(panel._cursor, 1)

    def test_double_press_opens_file(self):
        opened = []
        panel = self._make_panel(on_open_file=lambda f: opened.append(f))
        panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0]["name"], "welcome")

    def test_long_press_calls_on_back(self):
        called = []
        panel = self._make_panel(on_back=lambda: called.append(True))
        panel.handle_action("LONG_PRESS")
        self.assertTrue(called)

    def test_empty_state(self):
        panel = self._make_panel(files=[])
        self.assertEqual(panel._state, "empty")
        surface = pygame.Surface((240, 280))
        panel.render(surface)  # should not crash

    def test_renders_without_crash(self):
        panel = self._make_panel()
        surface = pygame.Surface((240, 280))
        panel.render(surface)

    def test_no_action_on_empty_list(self):
        panel = self._make_panel(files=[])
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._cursor, 0)
        panel.handle_action("DOUBLE_PRESS")  # no crash


if __name__ == "__main__":
    unittest.main()
