import pygame
from typing import TYPE_CHECKING
from device.input.handler import ButtonEvent

class Screen:
    """Base class for all BITOS screens."""
    SCREEN_NAME: str = "SCREEN"

    def __init__(self):
        self._manager = None

    def on_enter(self) -> None: pass
    def on_exit(self) -> None: pass
    def on_pause(self) -> None: pass
    def on_resume(self) -> None: pass
    def update(self, dt: float) -> None: pass

    def handle_event(self, event: ButtonEvent) -> bool:
        if event == ButtonEvent.DOUBLE_PRESS:
            if self._manager:
                self._manager.pop()
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        raise NotImplementedError

    def get_hint(self) -> str:
        return "[tap] scroll  [hold] select  [2x] back"

    def get_breadcrumb(self) -> str:
        return self.SCREEN_NAME

# Alias so manager.py can import either name
BaseScreen = Screen
