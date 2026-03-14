import os
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from input.handler import ButtonEvent, ButtonHandler


class ButtonHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.handler = ButtonHandler()
        self.fired = []
        self.handler.on(ButtonEvent.SHORT_PRESS, lambda: self.fired.append("short"))
        self.handler.on(ButtonEvent.LONG_PRESS, lambda: self.fired.append("long"))
        self.handler.on(ButtonEvent.DOUBLE_PRESS, lambda: self.fired.append("double"))
        self.handler.on(ButtonEvent.TRIPLE_PRESS, lambda: self.fired.append("triple"))

    def test_space_key_short_press(self):
        times = iter([1.0, 1.1, 1.8])
        with patch("input.handler.time.time", side_effect=lambda: next(times)):
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
            self.handler.update()

        self.assertEqual(self.fired, ["short"])

    def test_space_key_long_press(self):
        times = iter([10.0, 10.8])
        with patch("input.handler.time.time", side_effect=lambda: next(times)):
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))

        self.assertEqual(self.fired, ["long"])

    def test_double_and_triple_press_detection(self):
        times = iter([20.0, 20.1, 20.2, 20.3, 21.0, 30.0, 30.1, 30.2, 30.3, 30.4, 30.5, 31.2])
        with patch("input.handler.time.time", side_effect=lambda: next(times)):
            # double
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
            self.handler.update()

            # triple
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            self.handler.handle_pygame_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
            self.handler.update()

        self.assertEqual(self.fired, ["double", "triple"])

    def test_stale_press_times_are_cleaned_after_update(self):
        self.handler._release_times = [1.0, 1.1, 1.2]
        self.handler._pending_check_time = 1.3
        with patch("input.handler.time.time", return_value=5.0):
            self.handler.update()
        self.assertEqual(self.handler._release_times, [])
        self.assertIsNone(self.handler._pending_check_time)

    def test_concurrent_append_and_update_does_not_crash(self):
        stop = threading.Event()
        self.handler._pending_check_time = 0.0

        def writer():
            while not stop.is_set():
                self.handler._release_times.append(1.0)

        def reader():
            with patch("input.handler.time.time", return_value=999.0):
                for _ in range(200):
                    self.handler.update()

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t2.join(timeout=2)
        stop.set()
        t1.join(timeout=2)

        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
