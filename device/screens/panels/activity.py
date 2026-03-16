"""Activity Feed panel — unified feed of SMS, MAIL, CALENDAR, TASK items from /activity endpoint."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Literal

import pygame

from screens.base import BaseScreen
from display.tokens import (
    BLACK,
    WHITE,
    DIM2,
    DIM3,
    DIM4,
    HAIRLINE,
    PHYSICAL_W,
    PHYSICAL_H,
    STATUS_BAR_H,
)
from display.theme import merge_runtime_ui_settings, load_ui_font

logger = logging.getLogger(__name__)

# ── Feed item types and colors ────────────────────────────────
FEED_TYPES = ("ALL", "SMS", "MAIL", "CALENDAR", "TASK")

# Color bars per type (4px left accent)
_TYPE_COLORS: dict[str, tuple[int, int, int]] = {
    "AGENT": (0, 220, 220),       # cyan
    "SMS": (255, 100, 150),       # pink
    "MAIL": (160, 100, 255),      # purple
    "CALENDAR": (255, 180, 40),   # amber
    "TASK": (80, 220, 100),       # green
}

_TYPE_ICON = {
    "AGENT": "C",
    "SMS": "S",
    "MAIL": "M",
    "CALENDAR": "E",
    "TASK": "#",
}

CARD_H = 42          # card height in pixels
CARD_GAP = 3         # gap between cards
COLOR_BAR_W = 4      # left accent bar width
FILTER_TAB_H = 16    # filter tab row height
MAX_VISIBLE = 4      # max cards visible at once
POLL_INTERVAL_S = 30  # auto-refresh interval


@dataclass
class FeedItem:
    """Single activity feed entry."""
    id: str
    type: Literal["SMS", "MAIL", "CALENDAR", "TASK", "AGENT"]
    title: str
    body: str
    timestamp: float  # unix epoch
    read: bool = False
    source_id: str | None = None


def _relative_time(ts: float) -> str:
    """Convert unix timestamp to relative label like '3m', '1h', '2d'."""
    delta = time.time() - ts
    if delta < 60:
        return "now"
    if delta < 3600:
        return f"{int(delta / 60)}m"
    if delta < 86400:
        return f"{int(delta / 3600)}h"
    return f"{int(delta / 86400)}d"


class ActivityPanel(BaseScreen):
    """Scrollable activity feed with category filtering and auto-refresh."""

    _owns_status_bar = True

    def __init__(
        self,
        client,
        repository=None,
        on_back=None,
        ui_settings: dict | None = None,
    ):
        self._client = client
        self._repository = repository
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        self._lock = threading.Lock()
        self._items: list[FeedItem] = []
        self._filtered: list[FeedItem] = []
        self._state: str = "loading"  # loading | ready | empty | error
        self._cursor: int = 0
        self._filter_idx: int = 0  # index into FEED_TYPES
        self._load_thread: threading.Thread | None = None
        self._last_poll: float = 0.0
        self._active: bool = False
        self._unread_count: int = 0

    # ── Lifecycle ─────────────────────────────────────────────
    def on_enter(self):
        self._active = True
        self._fetch_activity()

    def on_exit(self):
        self._active = False

    def on_pause(self):
        self._active = False

    def on_resume(self):
        self._active = True
        self._fetch_activity()

    # ── Data fetching ─────────────────────────────────────────
    def _fetch_activity(self):
        if self._load_thread and self._load_thread.is_alive():
            return

        def _run():
            try:
                raw_items = self._client.get_activity()
                if raw_items:
                    items = [self._parse_item(raw) for raw in raw_items if isinstance(raw, dict)]
                    with self._lock:
                        self._items = items
                        self._apply_filter()
                        self._state = "ready" if items else "empty"
                        self._unread_count = sum(1 for i in items if not i.read)
                        self._last_poll = time.time()
                else:
                    with self._lock:
                        if not self._items:
                            self._state = "empty"
                        self._last_poll = time.time()
            except Exception as exc:
                logger.warning("activity_fetch_failed: %s", exc)
                with self._lock:
                    if not self._items:
                        self._state = "error"

        self._state = "loading" if not self._items else self._state
        self._load_thread = threading.Thread(target=_run, daemon=True)
        self._load_thread.start()

    def _parse_item(self, raw: dict) -> FeedItem:
        return FeedItem(
            id=str(raw.get("id", "")),
            type=raw.get("type", "AGENT"),
            title=str(raw.get("title", "")),
            body=str(raw.get("body", raw.get("message", ""))),
            timestamp=float(raw.get("timestamp", time.time())),
            read=bool(raw.get("read", False)),
            source_id=raw.get("source_id"),
        )

    def _apply_filter(self):
        """Filter items by current category. Must hold _lock."""
        active_type = FEED_TYPES[self._filter_idx]
        if active_type == "ALL":
            self._filtered = list(self._items)
        else:
            self._filtered = [i for i in self._items if i.type == active_type]
        # Clamp cursor
        if self._filtered:
            self._cursor = min(self._cursor, len(self._filtered) - 1)
        else:
            self._cursor = 0

    # ── Update (auto-refresh polling) ─────────────────────────
    def update(self, dt: float):
        if not self._active:
            return
        now = time.time()
        if now - self._last_poll >= POLL_INTERVAL_S:
            self._fetch_activity()

    # ── Input handling ────────────────────────────────────────
    def handle_input(self, event: pygame.event.Event):
        _ = event

    def handle_action(self, action: str):
        if action == "LONG_PRESS":
            if self._on_back:
                self._on_back()
            return

        with self._lock:
            if action == "SHORT_PRESS":
                # Cycle through cards
                if self._filtered:
                    self._cursor = (self._cursor + 1) % len(self._filtered)
                return

            if action == "TRIPLE_PRESS":
                # Cycle filter category
                self._filter_idx = (self._filter_idx + 1) % len(FEED_TYPES)
                self._apply_filter()
                return

            if action == "DOUBLE_PRESS":
                # Mark current item read + open detail
                if self._filtered:
                    item = self._filtered[self._cursor]
                    if not item.read:
                        item.read = True
                        self._unread_count = sum(1 for i in self._items if not i.read)
                        # Notify server in background
                        self._mark_read_remote(item.id)
                return

    def _mark_read_remote(self, item_id: str):
        def _run():
            self._client.mark_activity_read(item_id)
        threading.Thread(target=_run, daemon=True).start()

    # ── Badge count for status bar integration ────────────────
    @property
    def unread_count(self) -> int:
        with self._lock:
            return self._unread_count

    # ── Rendering ─────────────────────────────────────────────
    def _render_skeleton(self, surface, y, count=4):
        from display.skeleton import render_skeleton
        render_skeleton(surface, y, count)

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # ── Header: title + unread count ──
        title = self._font_small.render("ACTIVITY", False, WHITE)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        with self._lock:
            unread = self._unread_count
        if unread > 0:
            badge = self._font_small.render(str(unread), False, WHITE)
            surface.blit(badge, (PHYSICAL_W - badge.get_width() - 6, (STATUS_BAR_H - badge.get_height()) // 2))

        # ── Filter tabs ──
        tab_y = STATUS_BAR_H + 2
        self._render_filter_tabs(surface, tab_y)

        content_y = tab_y + FILTER_TAB_H + 2

        with self._lock:
            state = self._state
            items = list(self._filtered)
            cursor = self._cursor

        if state == "loading" and not items:
            self._render_skeleton(surface, content_y)
            return

        if state == "empty" or (state != "loading" and not items):
            label = self._font_body.render("NO ACTIVITY", False, DIM2)
            surface.blit(label, ((PHYSICAL_W - label.get_width()) // 2, PHYSICAL_H // 2))
            return

        if state == "error" and not items:
            label = self._font_body.render("OFFLINE", False, DIM3)
            surface.blit(label, ((PHYSICAL_W - label.get_width()) // 2, PHYSICAL_H // 2))
            return

        # ── Card list ──
        available_h = PHYSICAL_H - content_y - 4
        max_visible = max(1, available_h // (CARD_H + CARD_GAP))

        # Scroll window centered on cursor
        start = max(0, min(cursor, len(items) - max_visible))
        visible = items[start : start + max_visible]

        y = content_y
        for idx, item in enumerate(visible):
            actual_idx = start + idx
            focused = actual_idx == cursor
            self._render_card(surface, item, y, focused)
            y += CARD_H + CARD_GAP

    def _render_filter_tabs(self, surface: pygame.Surface, y: int):
        """Render category filter tabs across the top."""
        with self._lock:
            active_idx = self._filter_idx

        tab_w = PHYSICAL_W // len(FEED_TYPES)
        for idx, label in enumerate(FEED_TYPES):
            x = idx * tab_w
            selected = idx == active_idx
            if selected:
                pygame.draw.rect(surface, WHITE, (x, y, tab_w, FILTER_TAB_H))
                color = BLACK
            else:
                color = DIM3
            text = self._font_hint.render(label[:4], False, color)
            tx = x + (tab_w - text.get_width()) // 2
            ty = y + (FILTER_TAB_H - text.get_height()) // 2
            surface.blit(text, (tx, ty))

        # Bottom separator
        pygame.draw.line(surface, HAIRLINE, (0, y + FILTER_TAB_H), (PHYSICAL_W, y + FILTER_TAB_H))

    def _render_card(self, surface: pygame.Surface, item: FeedItem, y: int, focused: bool):
        """Render a single feed card with color bar, title, body preview, time."""
        # Background
        if focused:
            pygame.draw.rect(surface, WHITE, (0, y, PHYSICAL_W, CARD_H))
        else:
            pygame.draw.rect(surface, HAIRLINE, (0, y + CARD_H - 1, PHYSICAL_W, 1))

        # Color bar (4px on left)
        bar_color = _TYPE_COLORS.get(item.type, (128, 128, 128))
        pygame.draw.rect(surface, bar_color, (0, y, COLOR_BAR_W, CARD_H))

        # Text colors: brighter for unread, dimmed for read
        if focused:
            title_color = BLACK
            body_color = BLACK
            time_color = BLACK
        elif item.read:
            title_color = DIM3
            body_color = DIM4
            time_color = DIM4
        else:
            title_color = WHITE
            body_color = DIM2
            time_color = DIM2

        # Type icon + title (truncated ~20 chars)
        icon = _TYPE_ICON.get(item.type, "?")
        title_text = f"{icon} {item.title}"[:22]
        surface.blit(self._font_small.render(title_text, False, title_color), (COLOR_BAR_W + 4, y + 3))

        # Time label (right-aligned)
        time_label = _relative_time(item.timestamp)
        time_surf = self._font_hint.render(time_label, False, time_color)
        surface.blit(time_surf, (PHYSICAL_W - time_surf.get_width() - 4, y + 3))

        # Body preview (truncated ~24 chars)
        body_text = item.body[:26]
        surface.blit(self._font_hint.render(body_text, False, body_color), (COLOR_BAR_W + 4, y + 3 + self._font_small.get_height() + 3))

        # Unread dot indicator
        if not item.read and not focused:
            dot_x = PHYSICAL_W - 8
            dot_y = y + CARD_H // 2
            pygame.draw.circle(surface, WHITE, (dot_x, dot_y), 3)
