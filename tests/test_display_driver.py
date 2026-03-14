import os
import unittest
from pathlib import Path
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from display.driver import PygameDriver, ST7789Driver, create_driver


class DisplayDriverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.prev = os.environ.get("BITOS_DISPLAY")

    def tearDown(self):
        if self.prev is None:
            os.environ.pop("BITOS_DISPLAY", None)
        else:
            os.environ["BITOS_DISPLAY"] = self.prev

    def test_pygame_mode_returns_pygame_driver(self):
        os.environ["BITOS_DISPLAY"] = "pygame"
        drv = create_driver()
        self.assertIsInstance(drv, PygameDriver)

    def test_st7789_mode_returns_stub_driver_with_clean_error_on_init(self):
        os.environ["BITOS_DISPLAY"] = "st7789"
        drv = create_driver()
        self.assertIsInstance(drv, ST7789Driver)
        with self.assertRaises(NotImplementedError):
            drv.init()

    def test_pygame_driver_update_with_240x280_surface(self):
        drv = PygameDriver()
        drv.init()
        try:
            drv._surface = pygame.Surface((240, 280))
            drv.update()
        finally:
            drv.quit()

    def test_pygame_driver_update_with_480x560_surface(self):
        drv = PygameDriver()
        drv.init()
        try:
            drv._surface = pygame.Surface((480, 560))
            drv.update()
        finally:
            drv.quit()


if __name__ == "__main__":
    unittest.main()
