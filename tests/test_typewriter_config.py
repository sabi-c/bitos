"""Tests for TypewriterConfig — presets, custom config, char delays."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from display.typewriter import (
    TypewriterConfig,
    TypewriterRenderer,
    SPEED_PRESETS,
    _char_delay_ms,
)


class TestTypewriterConfig(unittest.TestCase):
    """Test TypewriterConfig dataclass and construction methods."""

    def test_defaults(self):
        cfg = TypewriterConfig()
        self.assertEqual(cfg.base_speed_ms, 45.0)
        self.assertEqual(cfg.punctuation_multiplier, 1.0)
        self.assertEqual(cfg.jitter_amount, 0.15)
        self.assertEqual(cfg.common_speedup, 0.8)
        self.assertEqual(cfg.rare_slowdown, 1.3)

    def test_from_preset_normal(self):
        cfg = TypewriterConfig.from_preset("normal")
        self.assertEqual(cfg.base_speed_ms, 45.0)

    def test_from_preset_slow(self):
        cfg = TypewriterConfig.from_preset("slow")
        self.assertEqual(cfg.base_speed_ms, 80.0)

    def test_from_preset_fast(self):
        cfg = TypewriterConfig.from_preset("fast")
        self.assertEqual(cfg.base_speed_ms, 20.0)

    def test_from_preset_instant(self):
        cfg = TypewriterConfig.from_preset("instant")
        self.assertEqual(cfg.base_speed_ms, 0.0)

    def test_from_preset_unknown_returns_default(self):
        cfg = TypewriterConfig.from_preset("nonexistent")
        self.assertEqual(cfg.base_speed_ms, 45.0)

    def test_from_dict_full(self):
        d = {
            "base_speed_ms": 60,
            "punctuation_multiplier": 2.0,
            "jitter_amount": 0.05,
            "common_speedup": 0.9,
            "rare_slowdown": 1.5,
        }
        cfg = TypewriterConfig.from_dict(d)
        self.assertEqual(cfg.base_speed_ms, 60.0)
        self.assertEqual(cfg.punctuation_multiplier, 2.0)
        self.assertEqual(cfg.jitter_amount, 0.05)
        self.assertEqual(cfg.common_speedup, 0.9)
        self.assertEqual(cfg.rare_slowdown, 1.5)

    def test_from_dict_partial_uses_defaults(self):
        cfg = TypewriterConfig.from_dict({"base_speed_ms": 100})
        self.assertEqual(cfg.base_speed_ms, 100.0)
        self.assertEqual(cfg.jitter_amount, 0.15)  # default

    def test_from_dict_empty_uses_defaults(self):
        cfg = TypewriterConfig.from_dict({})
        self.assertEqual(cfg.base_speed_ms, 45.0)

    def test_from_json_valid(self):
        cfg = TypewriterConfig.from_json('{"base_speed_ms": 30, "jitter_amount": 0.0}')
        self.assertEqual(cfg.base_speed_ms, 30.0)
        self.assertEqual(cfg.jitter_amount, 0.0)

    def test_from_json_invalid_returns_default(self):
        cfg = TypewriterConfig.from_json("not json")
        self.assertEqual(cfg.base_speed_ms, 45.0)

    def test_from_json_empty_string_returns_default(self):
        cfg = TypewriterConfig.from_json("")
        self.assertEqual(cfg.base_speed_ms, 45.0)

    def test_to_dict_roundtrip(self):
        cfg = TypewriterConfig(base_speed_ms=55, jitter_amount=0.2)
        d = cfg.to_dict()
        cfg2 = TypewriterConfig.from_dict(d)
        self.assertEqual(cfg, cfg2)


class TestSpeedPresets(unittest.TestCase):
    """Test SPEED_PRESETS mapping."""

    def test_all_presets_defined(self):
        self.assertIn("slow", SPEED_PRESETS)
        self.assertIn("normal", SPEED_PRESETS)
        self.assertIn("fast", SPEED_PRESETS)
        self.assertIn("instant", SPEED_PRESETS)

    def test_presets_ordered(self):
        self.assertGreater(SPEED_PRESETS["slow"], SPEED_PRESETS["normal"])
        self.assertGreater(SPEED_PRESETS["normal"], SPEED_PRESETS["fast"])
        self.assertGreater(SPEED_PRESETS["fast"], SPEED_PRESETS["instant"])


class TestCharDelayMs(unittest.TestCase):
    """Test _char_delay_ms function for different character types."""

    def setUp(self):
        # Use zero jitter for deterministic tests
        self.cfg = TypewriterConfig(base_speed_ms=50.0, jitter_amount=0.0)

    def test_common_letter_faster(self):
        delay = _char_delay_ms("e", self.cfg)
        base = _char_delay_ms("k", self.cfg)  # not common or rare
        self.assertLess(delay, base)

    def test_rare_letter_slower(self):
        delay = _char_delay_ms("z", self.cfg)
        base = _char_delay_ms("k", self.cfg)
        self.assertGreater(delay, base)

    def test_space_fast(self):
        delay = _char_delay_ms(" ", self.cfg)
        base = _char_delay_ms("k", self.cfg)
        self.assertLess(delay, base)

    def test_punctuation_adds_pause(self):
        delay_period = _char_delay_ms(".", self.cfg)
        delay_normal = _char_delay_ms("k", self.cfg)
        self.assertGreater(delay_period, delay_normal)

    def test_punctuation_multiplier_scales(self):
        cfg_low = TypewriterConfig(base_speed_ms=50.0, jitter_amount=0.0, punctuation_multiplier=0.5)
        cfg_high = TypewriterConfig(base_speed_ms=50.0, jitter_amount=0.0, punctuation_multiplier=2.0)
        delay_low = _char_delay_ms(".", cfg_low)
        delay_high = _char_delay_ms(".", cfg_high)
        self.assertGreater(delay_high, delay_low)

    def test_zero_jitter_deterministic(self):
        cfg = TypewriterConfig(base_speed_ms=50.0, jitter_amount=0.0)
        d1 = _char_delay_ms("a", cfg)
        d2 = _char_delay_ms("a", cfg)
        self.assertEqual(d1, d2)

    def test_newline_has_pause(self):
        delay = _char_delay_ms("\n", self.cfg)
        delay_normal = _char_delay_ms("k", self.cfg)
        self.assertGreater(delay, delay_normal)


class TestTypewriterRenderer(unittest.TestCase):
    """Test TypewriterRenderer lifecycle."""

    def test_initial_state(self):
        tw = TypewriterRenderer("Hello")
        self.assertFalse(tw.finished)
        self.assertEqual(tw.get_visible_text(), "")

    def test_instant_reveals_all(self):
        tw = TypewriterRenderer("Hello", speed="instant")
        self.assertTrue(tw.finished)
        self.assertEqual(tw.get_visible_text(), "Hello")

    def test_empty_text_finishes_immediately(self):
        tw = TypewriterRenderer("")
        self.assertTrue(tw.finished)

    def test_update_reveals_characters(self):
        cfg = TypewriterConfig(base_speed_ms=10.0, jitter_amount=0.0)
        tw = TypewriterRenderer("Hi", config=cfg)
        tw.update(0.05)  # 50ms > 10ms per char, should reveal both
        self.assertTrue(tw.finished)
        self.assertEqual(tw.get_visible_text(), "Hi")

    def test_reset_restarts(self):
        cfg = TypewriterConfig(base_speed_ms=10.0, jitter_amount=0.0)
        tw = TypewriterRenderer("Hi", config=cfg)
        tw.update(1.0)
        self.assertTrue(tw.finished)
        tw.reset("New", config=cfg)
        self.assertFalse(tw.finished)
        self.assertEqual(tw.get_visible_text(), "")

    def test_custom_config_overrides_speed(self):
        cfg = TypewriterConfig(base_speed_ms=1000.0, jitter_amount=0.0)
        tw = TypewriterRenderer("Hello", config=cfg)
        tw.update(0.01)  # 10ms — not enough for 1000ms base
        self.assertFalse(tw.finished)
        # Should have revealed at most the first character
        self.assertTrue(len(tw.get_visible_text()) <= 1)

    def test_preset_via_speed_param(self):
        tw = TypewriterRenderer("Test", speed="fast")
        # fast preset = 20ms, so 100ms should reveal all 4 chars
        tw.update(0.5)
        self.assertTrue(tw.finished)

    def test_reset_with_speed_param(self):
        tw = TypewriterRenderer("Hi", speed="fast")
        tw.update(1.0)
        tw.reset("Bye", speed="slow")
        self.assertFalse(tw.finished)


if __name__ == "__main__":
    unittest.main()
