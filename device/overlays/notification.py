"""Notification overlay primitives rendered above active screens."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame


_PRIORITY = {
    "CLAUDE": 4,
    "TASK": 3,
    "SMS": 2,
    "MAIL": 1,
}


@dataclass
class NotificationToast:
    """Overlay toast that renders above screens and expires by duration."""

    app: str
    icon: str
    message: str
    time_str: str
    duration_ms: int = 5000
    on_open: Callable[[], None] | None = None
    elapsed_ms: int = 0

    def render(self, surface, tokens) -> None:
        strip_h = 28
        pygame.draw.rect(surface, tokens.WHITE, pygame.Rect(0, 0, tokens.PHYSICAL_W, strip_h))

        try:
            font = pygame.font.Font(tokens.FONT_PATH, tokens.FONT_SIZES["small"])
        except FileNotFoundError:
            font = pygame.font.SysFont("monospace", tokens.FONT_SIZES["small"])
        left = f"{self.icon} {self.app}"[:14]
        msg = self.message[:24]
        right = self.time_str[:6]

        surface.blit(font.render(left, False, tokens.BLACK), (4, 3))
        surface.blit(font.render(right, False, tokens.BLACK), (tokens.PHYSICAL_W - 42, 3))
        surface.blit(font.render(msg, False, tokens.BLACK), (4, 14))

        progress_w = int(tokens.PHYSICAL_W * min(1.0, self.elapsed_ms / max(1, self.duration_ms)))
        pygame.draw.rect(surface, tokens.BLACK, pygame.Rect(0, strip_h - 2, progress_w, 2))

    def tick(self, dt_ms: int) -> bool:
        self.elapsed_ms += max(0, int(dt_ms))
        return self.elapsed_ms < self.duration_ms

    def handle_input(self, event) -> bool:
        action = event if isinstance(event, str) else None
        if action == "SHORT_PRESS":
            return False
        if action == "LONG_PRESS":
            if self.on_open:
                self.on_open()
            return False
        return True


class NotificationQueue:
    """At-most-3 queued toasts with domain-priority ordering."""

    def __init__(self):
        self._active: NotificationToast | None = None
        self._queue: list[NotificationToast] = []

    def push(self, toast: NotificationToast) -> None:
        if self._active is None:
            self._active = toast
            return

        pending = self._queue + [toast]
        pending.sort(key=self._priority_key, reverse=True)
        self._queue = pending[:3]

    def tick(self, dt_ms: int) -> None:
        if self._active is None and self._queue:
            self._active = self._queue.pop(0)
        if self._active is None:
            return
        alive = self._active.tick(dt_ms)
        if not alive:
            self._active = self._queue.pop(0) if self._queue else None

    def render(self, surface, tokens) -> None:
        if self._active is None:
            return
        self._active.render(surface, tokens)

    def handle_input(self, event) -> bool:
        if self._active is None:
            return False

        if not isinstance(event, str):
            return False
        keep = self._active.handle_input(event)
        if not keep:
            self._active = self._queue.pop(0) if self._queue else None
            return True
        return False

    @property
    def active(self) -> NotificationToast | None:
        return self._active

    @property
    def queued(self) -> list[NotificationToast]:
        return list(self._queue)

    def _priority_key(self, toast: NotificationToast) -> int:
        return _PRIORITY.get(str(toast.app).upper(), 0)
