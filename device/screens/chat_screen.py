"""Minimal chat voice screen."""

from __future__ import annotations

import pygame

from device.screens.base import Screen
from device.screens.registry import register_app


@register_app
class ChatScreen(Screen):
    SCREEN_NAME = "CHAT"
    MENU_ICON = "💬"
    MENU_ORDER = 1

    def __init__(self) -> None:
        super().__init__()
        self._pipeline = None
        self._state_display = "idle"

    def on_enter(self):
        manager = getattr(self, "_manager", None)
        if manager is None:
            return
        self._pipeline = getattr(manager, "_voice_pipeline", None)
        if self._pipeline:
            self._pipeline.on_state_change(self._on_state_change)
            self._state_display = self._pipeline.state

    def _on_state_change(self, state: str) -> None:
        self._state_display = state

    def handle_nav(self, action: str) -> bool:
        if not self._pipeline:
            return False
        if action == "HOLD_START":
            self._pipeline.start_recording()
            return True
        if action == "HOLD_END":
            self._pipeline.stop_and_process()
            return True
        if action == "BACK":
            self._pipeline.cancel()
            if self._manager:
                self._manager.pop()
            return True
        return False

    def handle_action(self, action: str):
        if action == "DOUBLE_PRESS":
            self.handle_nav("BACK")
            return
        if action in {"HOLD_START", "HOLD_END"}:
            self.handle_nav(action)

    def draw(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont("monospace", 16)
        text = self._state_display.upper()
        rendered = font.render(text, False, (255, 255, 255))
        rect = rendered.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2))
        surface.blit(rendered, rect)

    def render(self, surface: pygame.Surface) -> None:
        self.draw(surface)

    def get_hint(self) -> str:
        state = self._state_display
        if state == "recording":
            return "● RECORDING — release to send"
        if state == "transcribing":
            return "⟳ transcribing..."
        if state == "thinking":
            return "⟳ thinking..."
        if state == "speaking":
            return "♪ speaking..."
        return "[hold] speak  [2x] back"
