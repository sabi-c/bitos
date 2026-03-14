import json
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from bluetooth.auth import AuthError, AuthManager
from bluetooth.characteristics.keyboard_input import KeyboardInputCharacteristic
from client.api import BackendClient
from screens.manager import ScreenManager
from screens.panels.chat import ChatPanel


class KeyboardInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.auth = AuthManager(pin_hash="x", device_serial="s", ble_secret="11" * 32)

    def _token(self):
        t = "tok"
        self.auth._sessions[t] = 9999999999
        return t

    def test_valid_write_calls_callback(self):
        called = {"args": None}

        def cb(target, text, cursor):
            called["args"] = (target, text, cursor)
            return True

        ch = KeyboardInputCharacteristic(auth_manager=self.auth, on_keyboard_input=cb)
        payload = {"session_token": self._token(), "target": "compose_body", "text": "hello", "cursor_pos": 3}
        ch.WriteValue(json.dumps(payload).encode(), {})
        self.assertEqual(called["args"], ("compose_body", "hello", 3))

    def test_invalid_session_token_no_callback(self):
        fired = {"called": False}

        def cb(*_args):
            fired["called"] = True

        ch = KeyboardInputCharacteristic(auth_manager=self.auth, on_keyboard_input=cb)
        payload = {"session_token": "bad", "target": "compose_body", "text": "hello"}
        with self.assertRaises(AuthError):
            ch.WriteValue(json.dumps(payload).encode(), {})
        self.assertFalse(fired["called"])

    def test_screen_manager_set_compose_text_false_without_compose_screen(self):
        mgr = ScreenManager()
        self.assertFalse(mgr.set_compose_text("compose_body", "x", -1))

    def test_screen_manager_set_compose_text_true_for_chat(self):
        mgr = ScreenManager()
        panel = ChatPanel(client=BackendClient(base_url="http://localhost:1"))
        mgr.push(panel)
        self.assertTrue(mgr.set_compose_text("compose_body", "hello", -1))


if __name__ == "__main__":
    unittest.main()
