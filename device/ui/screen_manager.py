"""
BITOS Screen Manager
- Manages screen stack (push/pop)
- Translates ButtonEvent → NavigationEvent
- Draws status bar + hint bar over everything
- Routes CAPTURE and POWER gestures to global modals
"""
from __future__ import annotations

import logging
import time

import pygame

from device.screens.nav import NavigationEvent
from device.ui.draw_utils import draw_battery, draw_wifi
from device.ui.fonts import get_font

logger = logging.getLogger(__name__)

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DIM = (51, 51, 51)
MID = (85, 85, 85)
DARK = (10, 10, 10)

W, H = 240, 280
STATUS_H = 20
HINT_H = 20
CONTENT_H = H - STATUS_H - HINT_H


class ScreenManager:
    def __init__(self, surface: pygame.Surface | None = None, notification_queue=None, status_state=None):
        self._surf = surface
        self._stack: list = []
        self._modal = None
        self.notification_queue = notification_queue
        self._status_state = status_state

    @property
    def current(self):
        return self._stack[-1] if self._stack else None

    def _btn_to_nav(self, btn_event) -> str | None:
        from device.input.handler import ButtonEvent

        mapping = {
            ButtonEvent.SHORT_PRESS: NavigationEvent.NEXT,
            ButtonEvent.LONG_PRESS: NavigationEvent.SELECT,
            ButtonEvent.DOUBLE_PRESS: NavigationEvent.BACK,
            ButtonEvent.TRIPLE_PRESS: NavigationEvent.CAPTURE,
            ButtonEvent.POWER_GESTURE: NavigationEvent.POWER,
            ButtonEvent.HOLD_START: NavigationEvent.HOLD_START,
            ButtonEvent.HOLD_END: NavigationEvent.HOLD_END,
        }
        return mapping.get(btn_event)

    def handle_button_event(self, btn_event) -> None:
        nav = self._btn_to_nav(btn_event)
        if nav is not None:
            self.handle_nav(nav)

    # backward compatibility with legacy action strings
    def handle_action(self, action: str) -> None:
        mapping = {
            "SHORT_PRESS": NavigationEvent.NEXT,
            "LONG_PRESS": NavigationEvent.SELECT,
            "DOUBLE_PRESS": NavigationEvent.BACK,
            "TRIPLE_PRESS": NavigationEvent.CAPTURE,
        }
        nav = mapping.get(action)
        if nav:
            self.handle_nav(nav)

    def handle_nav(self, nav: str) -> None:
        if nav == NavigationEvent.CAPTURE:
            self._open_capture()
            return
        if nav == NavigationEvent.POWER:
            self._open_power_menu()
            return
        if self._modal is not None:
            self._route_nav(self._modal, nav)
            return
        if self._stack:
            self._route_nav(self._stack[-1], nav)

    def _route_nav(self, target, nav: str) -> None:
        if hasattr(target, "handle_nav"):
            target.handle_nav(nav)
            return
        if hasattr(target, "handle_action"):
            legacy = {
                NavigationEvent.NEXT: "SHORT_PRESS",
                NavigationEvent.SELECT: "LONG_PRESS",
                NavigationEvent.BACK: "DOUBLE_PRESS",
                NavigationEvent.CAPTURE: "TRIPLE_PRESS",
            }
            action = legacy.get(nav)
            if action:
                target.handle_action(action)

    def push(self, screen) -> None:
        if self._stack and hasattr(self._stack[-1], "on_pause"):
            self._stack[-1].on_pause()
        screen._manager = self
        self._stack.append(screen)
        if hasattr(screen, "on_enter"):
            screen.on_enter()

    def pop(self) -> None:
        if len(self._stack) <= 1:
            return
        screen = self._stack.pop()
        if hasattr(screen, "on_exit"):
            screen.on_exit()
        if self._stack and hasattr(self._stack[-1], "on_resume"):
            self._stack[-1].on_resume()

    def replace(self, screen) -> None:
        if self._stack:
            old = self._stack.pop()
            if hasattr(old, "on_exit"):
                old.on_exit()
        screen._manager = self
        self._stack.append(screen)
        if hasattr(screen, "on_enter"):
            screen.on_enter()

    def clear_to_home(self) -> None:
        from device.screens.home_screen import HomeScreen

        while len(self._stack) > 1:
            s = self._stack.pop()
            if hasattr(s, "on_exit"):
                s.on_exit()
        if self._stack:
            self.replace(HomeScreen())
        else:
            self.push(HomeScreen())

    def overlay(self, modal) -> None:
        modal._manager = self
        self._modal = modal
        if hasattr(modal, "on_enter"):
            modal.on_enter()

    def push_overlay(self, modal) -> None:
        self.overlay(modal)

    def dismiss_overlay(self, _overlay=None) -> None:
        if self._modal and hasattr(self._modal, "on_exit"):
            self._modal.on_exit()
        self._modal = None

    def _open_capture(self) -> None:
        try:
            from device.screens.modals.capture_modal import CaptureModal

            self.overlay(CaptureModal())
        except ImportError:
            logger.warning("CaptureModal not implemented yet")

    def _open_power_menu(self) -> None:
        try:
            from device.screens.modals.power_menu import PowerMenuModal

            self.overlay(PowerMenuModal())
        except ImportError:
            logger.warning("PowerMenuModal not implemented yet")

    # compatibility stubs
    def show_passkey_overlay(self, passkey: str, timeout_seconds: int = 30) -> None:
        logger.info("passkey overlay requested (%s sec)", timeout_seconds)

    def confirm_passkey(self) -> None:
        return

    def reject_passkey(self) -> None:
        return

    def attach_device_status_characteristic(self, _device_status_char) -> None:
        return

    def set_compose_text(self, target: str, text: str, cursor: int) -> bool:
        if self.current and hasattr(self.current, "receive_keyboard_input"):
            return bool(self.current.receive_keyboard_input(target=target, text=text, cursor=cursor))
        return False

    def show_shade(self, on_open_source=None) -> None:
        return

    def hide_shade(self) -> None:
        return

    def handle_input(self, event: pygame.event.Event):
        if self._modal and hasattr(self._modal, "handle_input"):
            self._modal.handle_input(event)
            return
        if self.current and hasattr(self.current, "handle_input"):
            self.current.handle_input(event)

    def update(self, dt: float) -> None:
        target = self._modal if self._modal else self.current
        if target and hasattr(target, "update"):
            target.update(dt)

    def draw(self, surface: pygame.Surface | None = None) -> None:
        if surface is not None:
            self._surf = surface
        if self._surf is None:
            return

        self._surf.fill(BLACK)
        content = pygame.Surface((W, CONTENT_H))
        content.fill(BLACK)

        active = self._modal if self._modal else self.current
        if active:
            try:
                if hasattr(active, "draw"):
                    active.draw(content)
                elif hasattr(active, "render"):
                    active.render(content)
            except Exception as exc:
                logger.error("draw error in %s: %s", getattr(active, "SCREEN_NAME", active.__class__.__name__), exc)

        self._surf.blit(content, (0, STATUS_H))
        self._draw_status_bar()

        hint = ""
        if self._modal and hasattr(self._modal, "get_hint"):
            hint = self._modal.get_hint()
        elif self.current and hasattr(self.current, "get_hint"):
            hint = self.current.get_hint()
        self._draw_hint_bar(hint)

    # legacy alias
    def render(self, surface: pygame.Surface) -> None:
        self.draw(surface)

    def _draw_status_bar(self) -> None:
        pygame.draw.rect(self._surf, WHITE, (0, 0, W, STATUS_H))
        now = time.localtime()
        h12 = now.tm_hour % 12 or 12
        t = f"{h12}:{now.tm_min:02d}"
        txt = get_font(6).render(t, False, BLACK)
        self._surf.blit(txt, (6, (STATUS_H - txt.get_height()) // 2))

        name = self.current_screen_name()
        ntxt = get_font(5).render(name, False, (80, 80, 80))
        self._surf.blit(ntxt, (W // 2 - ntxt.get_width() // 2, (STATUS_H - ntxt.get_height()) // 2))

        draw_wifi(self._surf, 190, 4, 14, 12, BLACK)
        draw_battery(self._surf, 208, 4, 18, 12, BLACK)

    def _draw_hint_bar(self, hint: str) -> None:
        y = H - HINT_H
        pygame.draw.rect(self._surf, DARK, (0, y, W, HINT_H))
        pygame.draw.line(self._surf, DIM, (0, y), (W, y))
        if hint:
            txt = get_font(5).render(hint, False, MID)
            self._surf.blit(txt, (W // 2 - txt.get_width() // 2, y + (HINT_H - txt.get_height()) // 2))

    def current_screen_name(self) -> str:
        if self._modal:
            return getattr(self._modal, "SCREEN_NAME", "MODAL")
        return getattr(self.current, "SCREEN_NAME", self.current.__class__.__name__) if self.current else "?"
