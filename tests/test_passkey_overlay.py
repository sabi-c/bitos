import os
import unittest
from pathlib import Path
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from overlays.passkey import PasskeyOverlay, _format_pin
import display.tokens as tokens


class PasskeyOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_renders_without_crash(self):
        overlay = PasskeyOverlay(passkey="123456")
        surface = pygame.Surface((240, 280))
        overlay.render(surface, tokens)

    def test_renders_confirmed_state_without_crash(self):
        overlay = PasskeyOverlay(passkey="999999")
        overlay.confirm()
        surface = pygame.Surface((240, 280))
        overlay.render(surface, tokens)

    def test_renders_failed_state_without_crash(self):
        overlay = PasskeyOverlay(passkey="999999")
        overlay.reject()
        surface = pygame.Surface((240, 280))
        overlay.render(surface, tokens)

    def test_handle_input_blocks_short_press(self):
        overlay = PasskeyOverlay(passkey="123456")
        result = overlay.handle_input("SHORT_PRESS")
        self.assertTrue(result)
        self.assertEqual(overlay.state, "showing")

    def test_handle_input_blocks_long_press(self):
        overlay = PasskeyOverlay(passkey="123456")
        result = overlay.handle_input("LONG_PRESS")
        self.assertTrue(result)
        self.assertEqual(overlay.state, "showing")

    def test_handle_input_double_press_cancels(self):
        overlay = PasskeyOverlay(passkey="123456")
        result = overlay.handle_input("DOUBLE_PRESS")
        self.assertTrue(result)
        self.assertEqual(overlay.state, "failed")

    def test_double_press_fires_on_cancelled(self):
        called = {"count": 0}

        def on_cancelled():
            called["count"] += 1

        overlay = PasskeyOverlay(passkey="123456", on_cancelled=on_cancelled)
        overlay.handle_input("DOUBLE_PRESS")
        self.assertEqual(called["count"], 1)

    def test_confirm_calls_on_confirmed(self):
        called = {"count": 0}

        def on_confirmed():
            called["count"] += 1

        overlay = PasskeyOverlay(passkey="123456", on_confirmed=on_confirmed)
        overlay.confirm()
        self.assertEqual(called["count"], 1)
        self.assertEqual(overlay.state, "confirmed")

    def test_reject_sets_failed_state(self):
        overlay = PasskeyOverlay(passkey="123456")
        overlay.reject()
        self.assertEqual(overlay.state, "failed")

    def test_is_active_true_while_showing(self):
        overlay = PasskeyOverlay(passkey="123456")
        self.assertTrue(overlay.is_active)

    def test_is_active_false_after_confirm(self):
        overlay = PasskeyOverlay(passkey="123456")
        overlay.confirm()
        self.assertFalse(overlay.is_active)

    def test_is_active_false_after_reject(self):
        overlay = PasskeyOverlay(passkey="123456")
        overlay.reject()
        self.assertFalse(overlay.is_active)

    def test_tick_returns_false_after_timeout(self):
        called = {"count": 0}

        def on_timeout():
            called["count"] += 1

        overlay = PasskeyOverlay(passkey="123456", on_timeout=on_timeout, timeout_seconds=2)
        # Tick past the timeout (2000ms + buffer)
        result = overlay.tick(2500)
        self.assertFalse(result)
        self.assertEqual(overlay.state, "timeout")
        self.assertEqual(called["count"], 1)

    def test_tick_returns_true_while_active(self):
        overlay = PasskeyOverlay(passkey="123456", timeout_seconds=30)
        result = overlay.tick(500)
        self.assertTrue(result)
        self.assertEqual(overlay.state, "showing")

    def test_pin_format_splits_into_groups(self):
        self.assertEqual(_format_pin("123456"), "123 456")

    def test_pin_format_pads_short_codes(self):
        self.assertEqual(_format_pin("42"), "000 042")

    def test_passkey_stored_padded(self):
        overlay = PasskeyOverlay(passkey="42")
        self.assertEqual(overlay.passkey, "000042")

    def test_blink_toggles_during_tick(self):
        overlay = PasskeyOverlay(passkey="123456", timeout_seconds=30)
        initial_blink = overlay._blink
        # Tick past blink interval (500ms)
        overlay.tick(600)
        self.assertNotEqual(overlay._blink, initial_blink)


class ScreenManagerPasskeyTests(unittest.TestCase):
    """Test show_passkey_overlay wiring into ScreenManager."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_show_passkey_overlay_creates_overlay(self):
        from screens.manager import ScreenManager
        mgr = ScreenManager()
        mgr.show_passkey_overlay("654321")
        self.assertIsNotNone(mgr._passkey_overlay)
        self.assertEqual(mgr._passkey_overlay.passkey, "654321")

    def test_confirm_passkey_clears_overlay(self):
        from screens.manager import ScreenManager
        mgr = ScreenManager()
        mgr.show_passkey_overlay("654321")
        mgr.confirm_passkey()
        self.assertIsNone(mgr._passkey_overlay)

    def test_reject_passkey_sets_failed_state(self):
        from screens.manager import ScreenManager
        mgr = ScreenManager()
        mgr.show_passkey_overlay("654321")
        mgr.reject_passkey()
        self.assertEqual(mgr._passkey_overlay.state, "failed")

    def test_hide_passkey_overlay_clears(self):
        from screens.manager import ScreenManager
        mgr = ScreenManager()
        mgr.show_passkey_overlay("654321")
        mgr.hide_passkey_overlay()
        self.assertIsNone(mgr._passkey_overlay)

    def test_passkey_overlay_blocks_actions(self):
        from screens.manager import ScreenManager
        mgr = ScreenManager()
        mgr.show_passkey_overlay("654321")
        # SHORT_PRESS should be consumed by overlay, not reach screens
        mgr.handle_action("SHORT_PRESS")
        self.assertTrue(mgr._passkey_overlay.is_active)


if __name__ == "__main__":
    unittest.main()
