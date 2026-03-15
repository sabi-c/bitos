import os
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from input.handler import ButtonEvent, ButtonHandler, create_button_handler


class BoardStub:
    def __init__(self):
        self.press_callbacks = []
        self.release_callbacks = []
        self._button_pressed = False

    def on_button_press(self, callback):
        self.press_callbacks.append(callback)

    def on_button_release(self, callback):
        self.release_callbacks.append(callback)

    def button_pressed(self):
        return self._button_pressed


class ButtonHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.handler = ButtonHandler()
        self.handler._poll_board_state = False  # keyboard tests don't need board polling
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

    def test_click_deadline_is_cleaned_after_update(self):
        self.handler._click_count = 1
        self.handler._click_deadline = 1.0
        with patch("input.handler.time.time", return_value=5.0):
            self.handler.update()
        self.assertEqual(self.handler._click_count, 0)
        self.assertIsNone(self.handler._click_deadline)

    def test_concurrent_press_release_and_update_does_not_crash(self):
        stop = threading.Event()

        def writer():
            while not stop.is_set():
                self.handler._on_press()
                self.handler._on_release()

        def reader():
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

    def test_create_button_handler_registers_board_callbacks(self):
        board = BoardStub()
        handler = create_button_handler(board=board)

        self.assertEqual(len(board.press_callbacks), 1)
        self.assertEqual(len(board.release_callbacks), 1)
        self.assertTrue(handler._poll_board_state)  # polling fallback enabled

        board.press_callbacks[0]()
        board.release_callbacks[0]()
        self.assertTrue(callable(handler.handle_pygame_event))

    def test_board_polling_fallback_when_edge_detection_fails(self):
        """Simulate edge detection failure: callbacks registered but never fire.
        Polling via board.button_pressed() should still detect presses."""
        board = BoardStub()
        handler = create_button_handler(board=board)

        fired = []
        handler.on(ButtonEvent.SHORT_PRESS, lambda: fired.append("short"))

        # Simulate: edge detection never fires callbacks.
        # Polling picks up button state via board.button_pressed().
        # update() calls time.time() once, then _on_press/_on_release call it again.
        times = iter([
            1.0, 1.0,    # update #1: now + _on_press
            1.1, 1.1,    # update #2: now + _on_release
            1.8,          # update #3: now (click deadline expires)
        ])
        with patch("input.handler.time.time", side_effect=lambda: next(times)):
            board._button_pressed = True
            handler.update()  # poll detects press
            board._button_pressed = False
            handler.update()  # poll detects release
            handler.update()  # click deadline expires → SHORT_PRESS

        self.assertEqual(fired, ["short"])

    def test_button_state_logs_include_active_screen(self):
        handler = ButtonHandler(active_screen_name_getter=lambda: "lock")

        times = iter([5.0, 5.1])  # press and release at distinct times (> debounce)
        with patch("input.handler.time.time", side_effect=lambda: next(times)):
            with patch("input.handler.logger.isEnabledFor", return_value=True), patch("input.handler.logger.debug") as log_debug:
                handler._on_press()
                handler._on_release()

        log_debug.assert_any_call("Button %s — active screen: %s", "pressed", "lock")
        log_debug.assert_any_call("Button %s — active screen: %s", "released", "lock")


if __name__ == "__main__":
    unittest.main()
