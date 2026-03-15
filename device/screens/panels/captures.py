"""Quick captures list panel."""
from __future__ import annotations

import logging
import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM2, DIM3, PHYSICAL_W, PHYSICAL_H, STATUS_BAR_H, ROW_H_MIN
from display.theme import merge_runtime_ui_settings, load_ui_font

logger = logging.getLogger(__name__)


class CapturesPanel(BaseScreen):
    def __init__(self, repository, on_back=None, ui_settings: dict | None = None):
        self._repository = repository
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._cursor = 0

    def _items(self):
        return self._repository.get_recent_captures(limit=25)

    def handle_input(self, event: pygame.event.Event):
        _ = event

    def handle_action(self, action: str):
        items = self._items()
        if action == "DOUBLE_PRESS":
            if self._on_back:
                self._on_back()
            return
        if not items:
            self._cursor = 0
            return
        self._cursor = min(self._cursor, len(items) - 1)
        if action == "SHORT_PRESS":
            self._cursor = (self._cursor + 1) % len(items)
        elif action == "TRIPLE_PRESS":
            self._cursor = (self._cursor - 1) % len(items)
        elif action == "LONG_PRESS":
            item = items[self._cursor]
            try:
                from pathlib import Path
                import sys
                sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "server"))
                from integrations.vikunja_adapter import VikunjaAdapter  # type: ignore
                created = VikunjaAdapter().create_task(item["text"])
                if created is not None:
                    self._repository.mark_capture_sent_to_vikunja(item["id"])
            except Exception as exc:
                logger.warning("capture_send_failed id=%s error=%s", item.get("id"), exc)

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)
        title = self._font_small.render("CAPTURES", False, WHITE)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))
        items = self._items()
        if not items:
            empty = self._font_body.render("NO CAPTURES YET", False, DIM3)
            surface.blit(empty, ((PHYSICAL_W - empty.get_width()) // 2, PHYSICAL_H // 2))
            return
        max_rows = max(1, (PHYSICAL_H - STATUS_BAR_H - 6) // ROW_H_MIN)
        start = min(self._cursor, max(0, len(items) - max_rows))
        visible = items[start : start + max_rows]
        y = STATUS_BAR_H + 2
        for idx, item in enumerate(visible):
            actual = start + idx
            focused = actual == self._cursor
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            color = BLACK if focused else WHITE
            meta = f"{item['created_at'][11:16]} {item['text'][:40]}"
            surface.blit(self._font_small.render(meta, False, color if focused else DIM2), (6, y + 2))
            surface.blit(self._font_body.render(item['text'][:40], False, color), (6, y + self._font_small.get_height() + 4))
            y += ROW_H_MIN
