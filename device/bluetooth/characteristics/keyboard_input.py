"""Protected keyboard input characteristic."""
from __future__ import annotations

import json
from typing import Callable

from bluetooth.auth import AuthError, AuthManager


class KeyboardInputCharacteristic:
    """Receives full-field keyboard updates from companion client."""

    def __init__(self, auth_manager: AuthManager, on_keyboard_input: Callable[[str, str, int], bool | None]):
        self._auth_manager = auth_manager
        self._on_keyboard_input = on_keyboard_input

    def WriteValue(self, value, _options):
        payload = json.loads(bytes(value).decode("utf-8"))
        session_token = str(payload.get("session_token", ""))
        if not self._auth_manager.validate_session_token(session_token):
            raise AuthError("INVALID_SESSION_TOKEN")

        target = str(payload.get("target", "any"))
        text = str(payload.get("text", ""))
        cursor_pos = int(payload.get("cursor_pos", -1))
        self._on_keyboard_input(target, text, cursor_pos)
