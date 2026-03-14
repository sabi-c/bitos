"""BITOS screen base abstractions."""
from abc import ABC, abstractmethod
import pygame


class BaseScreen(ABC):
    """Abstract base for all screens."""

    @abstractmethod
    def render(self, surface: pygame.Surface):
        """Draw this screen to the surface."""

    @abstractmethod
    def handle_input(self, event: pygame.event.Event):
        """Process keyboard/mouse input events."""

    def handle_action(self, action: str):
        """Process high-level button actions (SHORT_PRESS, LONG_PRESS, etc.)."""

    def update(self, dt: float):
        """Update logic per frame. Override if needed."""

    def on_enter(self):
        """Called when this screen becomes active."""

    def on_exit(self):
        """Called when this screen is removed."""
