"""Tests for TypewriterRenderer (character-level)."""
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

    def test_progressive_reveal_character_level(self):
        tw = TypewriterRenderer("Hello", speed="normal")
        # At 30ms/char base, after 0.05s we should have some but not all chars
        tw.update(0.05)
        visible = tw.get_visible_text()
        self.assertTrue(len(visible) > 0)
        self.assertTrue(len(visible) < 5)

        # After enough time, all chars revealed
        tw.update(2.0)
        self.assertEqual(tw.get_visible_text(), "Hello")

    def test_finished_property(self):
        tw = TypewriterRenderer("Hi", speed="instant")
        self.assertTrue(tw.finished)  # instant finishes immediately
        self.assertEqual(tw.get_visible_text(), "Hi")

    def test_period_adds_pause(self):
        tw = TypewriterRenderer("A. B", speed="fast")
        # At 15ms/char base, 'A' reveals fast, but '.' adds 280ms pause
        tw.update(0.03)  # Should have 'A' and '.'
        visible = tw.get_visible_text()
        self.assertIn("A", visible)
        # Space after period should be delayed by the 280ms pause
        tw.update(0.1)  # total ~0.13s, period pause is 0.28s
        self.assertNotIn("B", tw.get_visible_text())
        tw.update(0.3)  # total ~0.43s, past the pause
        self.assertIn("B", tw.get_visible_text())

    def test_speed_presets_exist(self):
        for preset in ("slow", "normal", "fast", "instant"):
            self.assertIn(preset, SPEED_PRESETS)

    def test_reset(self):
        tw = TypewriterRenderer("Hello world", speed="instant")
        self.assertTrue(tw.finished)
        tw.reset("New text")
        self.assertTrue(tw.finished)  # still instant speed
        tw.reset("New text", speed="normal")
        self.assertFalse(tw.finished)
        self.assertEqual(tw.get_visible_text(), "")

    def test_slow_preset_uses_80ms_base(self):
        tw = TypewriterRenderer("hi", speed="slow")
        tw.update(0.05)  # 50ms — should reveal at most 1 char
        self.assertLess(len(tw.get_visible_text()), 2)

    def test_full_reveal(self):
        text = "The quick brown fox."
        tw = TypewriterRenderer(text, speed="normal")
        # Run enough time to reveal everything
        tw.update(10.0)
        self.assertTrue(tw.finished)
        self.assertEqual(tw.get_visible_text(), text)


if __name__ == "__main__":
    unittest.main()
