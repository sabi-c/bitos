"""Tests for TypewriterRenderer."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from display.typewriter import TypewriterRenderer, SPEED_PRESETS


class TypewriterTests(unittest.TestCase):
    def test_instant_reveals_all(self):
        tw = TypewriterRenderer("Hello world", speed="instant")
        tw.update(0.01)
        self.assertEqual(tw.get_visible_text(), "Hello world")

    def test_empty_text(self):
        tw = TypewriterRenderer("", speed="normal")
        tw.update(1.0)
        self.assertEqual(tw.get_visible_text(), "")

    def test_progressive_reveal(self):
        tw = TypewriterRenderer("one two three", speed="normal")
        # At 3 words/sec, all 3 words take ~1s to fully reveal
        tw.update(0.5)
        visible = tw.get_visible_text()
        self.assertIn("one", visible)
        self.assertNotIn("three", visible)
        tw.update(1.0)
        self.assertIn("three", tw.get_visible_text())

    def test_finished_property(self):
        tw = TypewriterRenderer("Hi", speed="instant")
        self.assertFalse(tw.finished)
        tw.update(0.01)
        self.assertTrue(tw.finished)

    def test_period_adds_pause(self):
        tw = TypewriterRenderer("End. Start", speed="fast")
        tw.update(0.2)
        visible_after_first = tw.get_visible_text()
        self.assertIn("End.", visible_after_first)
        tw.update(0.1)
        self.assertNotIn("Start", tw.get_visible_text())
        tw.update(0.5)  # Total 0.8s > 0.734s threshold (0.167 + 0.167 + 0.4)
        self.assertIn("Start", tw.get_visible_text())

    def test_speed_presets_exist(self):
        for preset in ("slow", "normal", "fast", "instant"):
            self.assertIn(preset, SPEED_PRESETS)

    def test_reset(self):
        tw = TypewriterRenderer("Hello world", speed="instant")
        tw.update(1.0)
        self.assertTrue(tw.finished)
        tw.reset("New text")
        self.assertFalse(tw.finished)
        self.assertEqual(tw.get_visible_text(), "")


if __name__ == "__main__":
    unittest.main()
