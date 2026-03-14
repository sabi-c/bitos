"""BITOS Screen Manager: stack + simple route transitions."""
import pygame

import display.tokens as tokens
from display.tokens import BLACK, WHITE
from overlays import NotificationQueue, NotificationShade, PasskeyOverlay
from screens.base import BaseScreen


class ScreenManager:
    """Manages a stack of screens. Top screen receives render + input."""

    def __init__(self, notification_queue: NotificationQueue | None = None):
        self._stack: list[BaseScreen] = []
        self._flash_frames = 0
        self.notification_queue = notification_queue or NotificationQueue()
        self._notification_shade: NotificationShade | None = None
        self._passkey_overlay: PasskeyOverlay | None = None
        self._device_status_char = None

    def push(self, screen: BaseScreen):
        if self._stack:
            self._stack[-1].on_exit()
            self._flash_frames = 2
        self._stack.append(screen)
        screen.on_enter()
        self._emit_active_screen_status()

    def pop(self) -> BaseScreen | None:
        if not self._stack:
            return None
        screen = self._stack.pop()
        screen.on_exit()
        if self._stack:
            self._flash_frames = 2
            self._stack[-1].on_enter()
        self._emit_active_screen_status()
        return screen

    def replace(self, screen: BaseScreen):
        if self._stack:
            self._stack[-1].on_exit()
            self._stack.pop()
        self._flash_frames = 2
        self._stack.append(screen)
        screen.on_enter()
        self._emit_active_screen_status()

    def show_shade(self, on_open_source=None) -> None:
        self._notification_shade = NotificationShade(
            queue=self.notification_queue,
            on_close=self.hide_shade,
            on_open_source=on_open_source,
        )

    def hide_shade(self) -> None:
        self._notification_shade = None


    def show_passkey_overlay(self, code: str, timeout_s: int = 120) -> None:
        self._passkey_overlay = PasskeyOverlay(code=code, timeout_s=timeout_s, on_timeout=self.hide_passkey_overlay)

    def hide_passkey_overlay(self) -> None:
        self._passkey_overlay = None

    def attach_device_status_characteristic(self, device_status_char) -> None:
        self._device_status_char = device_status_char
        self._emit_active_screen_status()

    def get_active_compose_target(self) -> str | None:
        if not self.current:
            return None
        getter = getattr(self.current, "get_active_compose_target", None)
        if callable(getter):
            return getter()
        return None

    def set_compose_text(self, target: str, text: str, cursor: int) -> bool:
        if not self.current:
            return False
        writer = getattr(self.current, "receive_keyboard_input", None)
        if not callable(writer):
            return False
        result = writer(target=target, text=text, cursor=cursor)
        return bool(result)

    def _emit_active_screen_status(self) -> None:
        if self._device_status_char is None:
            return
        name = self.current.__class__.__name__.replace("Panel", "").replace("Screen", "").lower() if self.current else "none"
        self._device_status_char.update_and_notify({"active_screen": name})

    @property
    def current(self) -> BaseScreen | None:
        return self._stack[-1] if self._stack else None

    def handle_input(self, event: pygame.event.Event):
        if self.notification_queue.handle_input(event):
            return
        if self.current:
            self.current.handle_input(event)

    def handle_action(self, action: str):
        if self._passkey_overlay and self._passkey_overlay.handle_input(action):
            return
        if self.notification_queue.handle_input(action):
            return
        if self._notification_shade and self._notification_shade.handle_input(action):
            return
        if self.current:
            self.current.handle_action(action)

    def update(self, dt: float):
        dt_ms = int(max(0.0, dt) * 1000)
        self.notification_queue.tick(dt_ms)
        if self._passkey_overlay and not self._passkey_overlay.tick(dt_ms):
            self._passkey_overlay = None
        if self.current:
            self.current.update(dt)

    def render_overlay(self, surface: pygame.Surface):
        if self._notification_shade:
            self._notification_shade.render(surface, tokens)
        if self._passkey_overlay:
            self._passkey_overlay.render(surface, tokens)
        self.notification_queue.render(surface, tokens)

    def render(self, surface: pygame.Surface):
        if self._flash_frames > 0:
            surface.fill(WHITE)
            self._flash_frames -= 1
            return

        surface.fill(BLACK)
        if self.current:
            self.current.render(surface)
        self.render_overlay(surface)
