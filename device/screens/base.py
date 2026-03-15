"""
BITOS Screen Base Class
Subclass this for every screen. ScreenManager calls these methods.

IMPORTANT: Screens receive NavigationEvent, NOT ButtonEvent.
Do not import from device.input.handler in screen files.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pygame

from device.screens.nav import NavigationEvent


class Screen:
    SCREEN_NAME: str = "SCREEN"
    MENU_ICON: str = "?"
    MENU_ORDER: int = 99

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

    def update(self, dt: float) -> None:
        pass

    def handle_nav(self, event: str) -> bool:
        if event == NavigationEvent.BACK:
            if self._manager:
                self._manager.pop()
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        raise NotImplementedError(f"{self.__class__.__name__} must implement draw()")

    def get_hint(self) -> str:
        return "[tap] scroll  [hold] select  [2x] back"


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
