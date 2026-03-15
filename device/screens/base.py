import pygame
from device.input.handler import ButtonEvent

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


class Screen:
    SCREEN_NAME: str = "SCREEN"

    def __init__(self):
        self._manager = None

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_pause(self):
        pass

    def on_resume(self):
        pass

    def update(self, dt: float):
        pass

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
