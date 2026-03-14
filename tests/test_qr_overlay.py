import os
import unittest
from pathlib import Path
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from overlays.qr_code import QROverlay


class QROverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_init_without_crash(self):
        overlay = QROverlay(url="https://example.com", title="TITLE", subtitle="SUB")
        self.assertIsNotNone(overlay)

    def test_tick_timeout(self):
        overlay = QROverlay(url="https://example.com", title="TITLE", subtitle="SUB", timeout_s=1)
        self.assertFalse(overlay.tick(1000))

    def test_tick_active(self):
        overlay = QROverlay(url="https://example.com", title="TITLE", subtitle="SUB", timeout_s=10)
        self.assertTrue(overlay.tick(100))

    def test_handle_long_press_calls_dismiss(self):
        fired = {"n": 0}
        overlay = QROverlay(
            url="https://example.com",
            title="TITLE",
            subtitle="SUB",
            on_dismiss=lambda: fired.__setitem__("n", fired["n"] + 1),
        )
        self.assertFalse(overlay.handle_input("LONG_PRESS"))
        self.assertEqual(fired["n"], 1)

    def test_handle_double_press_calls_dismiss(self):
        fired = {"n": 0}
        overlay = QROverlay(
            url="https://example.com",
            title="TITLE",
            subtitle="SUB",
            on_dismiss=lambda: fired.__setitem__("n", fired["n"] + 1),
        )
        self.assertFalse(overlay.handle_input("DOUBLE_PRESS"))
        self.assertEqual(fired["n"], 1)

    def test_notify_connected_fires_callback(self):
        fired = {"n": 0}
        overlay = QROverlay(
            url="https://example.com",
            title="TITLE",
            subtitle="SUB",
            on_connected=lambda: fired.__setitem__("n", fired["n"] + 1),
        )
        overlay.notify_connected()
        self.assertEqual(fired["n"], 1)

    def test_url_builders(self):
        os.environ.pop("BITOS_COMPANION_URL", None)
        from importlib import reload
        import bluetooth.constants as constants

        reload(constants)
        self.assertEqual(constants.build_setup_url("AA:BB"), "https://bitos-p8xw.onrender.com/setup.html?ble=AA:BB&v=1")
        self.assertEqual(constants.build_pair_url("AA:BB"), "https://bitos-p8xw.onrender.com/pair.html?ble=AA:BB&v=1")

    def test_env_override_companion_url(self):
        os.environ["BITOS_COMPANION_URL"] = "https://example.test"
        from importlib import reload
        import bluetooth.constants as constants

        reload(constants)
        self.assertEqual(constants.build_setup_url("AA:BB"), "https://example.test/setup.html?ble=AA:BB&v=1")


if __name__ == "__main__":
    unittest.main()
