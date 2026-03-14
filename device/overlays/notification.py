"""Notification overlay primitives rendered above active screens."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import pygame


_PRIORITY = {
    "CLAUDE": 4,
    "TASK": 3,
    "SMS": 2,
    "MAIL": 1,
}

_TYPE_ICON = {
    "CLAUDE": "C",
    "TASK": "#",
    "SMS": "S",
    "MAIL": "M",
}


@dataclass
class NotificationRecord:
    id: str
    type: Literal["CLAUDE", "TASK", "SMS", "MAIL"]
    app_name: str
    message: str
    time_str: str
    read: bool = False
    source_id: str | None = None


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


class NotificationShade:
    """Full-screen notification list overlay rendered above the screen stack."""

    def __init__(
        self,
        queue: "NotificationQueue",
        on_close: Callable[[], None] | None = None,
        on_open_source: Callable[[str], None] | None = None,
    ):
        self._queue = queue
        self._on_close = on_close
        self._on_open_source = on_open_source
        self._cursor_index = 0

    def render(self, surface, tokens) -> None:
        records = self._queue.get_all()
        surface.fill(tokens.BLACK)

        pygame.draw.rect(surface, tokens.WHITE, pygame.Rect(0, 0, tokens.PHYSICAL_W, 20))
        header_font = self._font(tokens, "small")
        body_font = self._font(tokens, "body")
        app_font = self._font(tokens, "small")

        unread = sum(1 for item in records if not item.read)
        surface.blit(header_font.render("NOTIFICATIONS", False, tokens.BLACK), (4, 6))
        surface.blit(header_font.render(str(unread), False, tokens.BLACK), (tokens.PHYSICAL_W - 14, 6))

        if not records:
            empty = body_font.render("NO NOTIFICATIONS", False, tokens.DIM3)
            surface.blit(empty, ((tokens.PHYSICAL_W - empty.get_width()) // 2, 136))
            return

        row_h = 18
        max_rows = max(1, (tokens.PHYSICAL_H - 24) // row_h)
        start = 0
        if self._cursor_index >= max_rows:
            start = self._cursor_index - max_rows + 1
        visible = records[start : start + max_rows]

        for idx, record in enumerate(visible):
            y = 24 + idx * row_h
            actual_idx = start + idx
            selected = actual_idx == self._cursor_index
            if selected:
                pygame.draw.rect(surface, tokens.DIM4, pygame.Rect(2, y - 1, tokens.PHYSICAL_W - 4, row_h - 1))

            self._render_dot(surface, tokens, record, 5, y + 5)
            app_text = f"{_TYPE_ICON.get(record.type, '?')} {record.app_name}"[:12]
            msg_text = record.message[:19]

            app_color = tokens.WHITE if not record.read else tokens.DIM2
            msg_color = tokens.WHITE if not record.read else tokens.DIM3

            surface.blit(app_font.render(app_text, False, app_color), (14, y + 1))
            surface.blit(app_font.render(record.time_str[:5], False, tokens.DIM2), (tokens.PHYSICAL_W - 34, y + 1))
            surface.blit(body_font.render(msg_text, False, msg_color), (14, y + 8))

    def handle_input(self, action: str) -> bool:
        records = self._queue.get_all()
        if action == "DOUBLE_PRESS":
            if self._on_close:
                self._on_close()
            return True

        if not records:
            return action in {"SHORT_PRESS", "LONG_PRESS"}

        if action == "SHORT_PRESS":
            self._cursor_index = (self._cursor_index + 1) % len(records)
            return True

        if action == "LONG_PRESS":
            record = records[self._cursor_index]
            self._queue.mark_read(record.id)
            source = record.source_id or record.id
            if self._on_open_source:
                self._on_open_source(source)
            return True

        return False

    def _font(self, tokens, key: str):
        try:
            return pygame.font.Font(tokens.FONT_PATH, tokens.FONT_SIZES[key])
        except FileNotFoundError:
            return pygame.font.SysFont("monospace", tokens.FONT_SIZES[key])

    def _render_dot(self, surface, tokens, record: NotificationRecord, x: int, y: int) -> None:
        if record.type == "TASK":
            pygame.draw.rect(surface, tokens.WHITE, pygame.Rect(x, y, 4, 4))
            return
        pygame.draw.circle(surface, tokens.WHITE, (x + 2, y + 2), 2)


class NotificationQueue:
    """Queued toasts + persisted notification records."""

    def __init__(self, repository=None):
        self._repository = repository
        self._active: NotificationToast | None = None
        self._queue: list[NotificationToast] = []

    def push(self, toast: NotificationToast) -> None:
        if self._active is None:
            self._active = toast
            return

        pending = self._queue + [toast]
        pending.sort(key=self._priority_key, reverse=True)
        self._queue = pending[:3]

    def push_record(self, record: NotificationRecord) -> None:
        if self._repository is not None:
            self._repository.add_notification(record)
            self._repository.trim_notifications(max_rows=50)
        self.push(
            NotificationToast(
                app=record.app_name,
                icon=_TYPE_ICON.get(record.type, "N"),
                message=record.message,
                time_str=record.time_str,
            )
        )

    def get_all(self) -> list[NotificationRecord]:
        if self._repository is None:
            return []
        rows = self._repository.list_notifications(limit=50)
        return [
            NotificationRecord(
                id=row["id"],
                type=row["type"],
                app_name=row["app_name"],
                message=row["message"],
                time_str=row["time_str"],
                read=bool(row["read"]),
                source_id=row["source_id"],
            )
            for row in rows
        ]

    def mark_read(self, notification_id: str) -> None:
        if self._repository is not None:
            self._repository.mark_notification_read(notification_id)

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
