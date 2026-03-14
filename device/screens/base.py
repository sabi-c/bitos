"""
BITOS Screen Base + Manager
Manages a stack of screens with white-flash transitions.
"""
from abc import ABC, abstractmethod
import pygame

from display.tokens import BLACK, WHITE, PHYSICAL_W, PHYSICAL_H


class BaseScreen(ABC):
    """Abstract base for all screens."""

    @abstractmethod
    def render(self, surface: pygame.Surface):
        """Draw this screen to the surface."""
        pass

    @abstractmethod
    def handle_input(self, event: pygame.event.Event):
        """Process input events."""
        pass

    def update(self, dt: float):
        """Update logic per frame. Override if needed."""
        pass

    def on_enter(self):
        """Called when this screen becomes active."""
        pass

    def on_exit(self):
        """Called when this screen is removed."""
        pass
