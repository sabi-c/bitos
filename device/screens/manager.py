"""
BITOS Screen Manager
Push/pop screen stack with white-flash transition.
"""
import pygame
from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, PHYSICAL_W, PHYSICAL_H


class ScreenManager:
    """Manages a stack of screens. Top screen receives render + input."""

    def __init__(self):
        self._stack: list[BaseScreen] = []
        self._flash_frames = 0  # White flash transition counter

    def push(self, screen: BaseScreen):
        """Push a new screen on top. Triggers white flash."""
        if self._stack:
            self._stack[-1].on_exit()
            self._flash_frames = 2  # 2 frames of white
        self._stack.append(screen)
        screen.on_enter()

    def pop(self) -> BaseScreen | None:
        """Pop top screen. Returns it."""
        if not self._stack:
            return None
        screen = self._stack.pop()
        screen.on_exit()
        if self._stack:
            self._flash_frames = 2
            self._stack[-1].on_enter()
        return screen

    def replace(self, screen: BaseScreen):
        """Replace top screen (pop + push without double flash)."""
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
