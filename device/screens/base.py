"""
BITOS Screen Base Class
Every screen subclasses this. ScreenManager calls these methods.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from device.input.handler import ButtonEvent


class Screen:
    """Base class for all BITOS screens."""

    SCREEN_NAME: str = "SCREEN"

    def __init__(self):
        self._manager = None

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass

    def on_pause(self) -> None:
        pass

    def on_resume(self) -> None:
        pass

    def handle_event(self, event: "ButtonEvent") -> bool:
        """Handle button events; default double-press pops current screen."""
        from device.input.handler import ButtonEvent

        if event == ButtonEvent.DOUBLE_PRESS:
            if self._manager:
                self._manager.pop()
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        """Draw this screen to the content surface (240x240)."""
        raise NotImplementedError

    def get_hint(self) -> str:
        return "[tap] scroll  [hold] select  [2x] back"

    def get_breadcrumb(self) -> str:
        return self.SCREEN_NAME

    def update(self, dt: float) -> None:
        pass


class BaseScreen(ABC):
    """Legacy abstraction retained for compatibility with existing manager."""

    _owns_status_bar: bool = False

    @abstractmethod
    def render(self, surface: pygame.Surface):
        """Draw this screen to the surface."""

    @abstractmethod
    def handle_input(self, event: pygame.event.Event):
        """Process keyboard/mouse input events."""

    def handle_action(self, action: str):
        """Process high-level button actions."""

    def update(self, dt: float):
        """Update logic per frame. Override if needed."""

    def on_enter(self):
        """Called when this screen becomes active."""

    def on_exit(self):
        """Called when this screen is removed."""
