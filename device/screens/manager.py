"""BITOS Screen Manager: stack + simple route transitions."""
import pygame
from screens.base import BaseScreen
from display.tokens import BLACK, WHITE


class ScreenManager:
    """Manages a stack of screens. Top screen receives render + input."""

    def __init__(self):
        self._stack: list[BaseScreen] = []
        self._flash_frames = 0

    def push(self, screen: BaseScreen):
        if self._stack:
            self._stack[-1].on_exit()
            self._flash_frames = 2
        self._stack.append(screen)
        screen.on_enter()

    def pop(self) -> BaseScreen | None:
        if not self._stack:
            return None
        screen = self._stack.pop()
        screen.on_exit()
        if self._stack:
            self._flash_frames = 2
            self._stack[-1].on_enter()
        return screen

    def replace(self, screen: BaseScreen):
        if self._stack:
            self._stack[-1].on_exit()
            self._stack.pop()
        self._flash_frames = 2
        self._stack.append(screen)
        screen.on_enter()

    @property
    def current(self) -> BaseScreen | None:
        return self._stack[-1] if self._stack else None

    def handle_input(self, event: pygame.event.Event):
        if self.current:
            self.current.handle_input(event)

    def handle_action(self, action: str):
        if self.current:
            self.current.handle_action(action)

    def update(self, dt: float):
        if self.current:
            self.current.update(dt)

    def render(self, surface: pygame.Surface):
        if self._flash_frames > 0:
            surface.fill(WHITE)
            self._flash_frames -= 1
            return

        surface.fill(BLACK)
        if self.current:
            self.current.render(surface)
