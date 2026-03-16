"""Tests for ActionBar component."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

_repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_repo / "device"))
sys.path.insert(0, str(_repo))

from ui.components.action_bar import ActionBar


class ActionBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_default_actions(self):
        bar = ActionBar()
        self.assertEqual(len(bar.actions), 3)

    def test_set_actions(self):
        bar = ActionBar()
        bar.set_actions([("tap", "SEND"), ("hold", "CANCEL")])
        self.assertEqual(len(bar.actions), 2)
        self.assertEqual(bar.actions[0], ("tap", "SEND"))

    def test_set_text_fallback(self):
        bar = ActionBar()
        bar.set_text("listening...")
        self.assertEqual(bar.text, "listening...")
        self.assertEqual(len(bar.actions), 0)

    def test_icon_types_valid(self):
        bar = ActionBar()
        bar.set_actions([("tap", "A"), ("double", "B"), ("hold", "C")])
        for icon_type, _ in bar.actions:
            self.assertIn(icon_type, ("tap", "double", "hold"))

    def test_reset_to_defaults(self):
        bar = ActionBar()
        bar.set_text("something")
        bar.set_actions([("tap", "NEXT"), ("double", "SELECT"), ("hold", "BACK")])
        self.assertEqual(len(bar.actions), 3)
        self.assertEqual(bar.text, "")


if __name__ == "__main__":
    unittest.main()
