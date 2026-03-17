"""FieldRecordingPanel — preview panel for RECORD sidebar item.

Shows: NEW RECORDING action, recent recordings list, BACK TO MAIN MENU.
Recording state machine: IDLE -> RECORDING -> SAVING -> DONE.
During RECORDING: pulsing red dot + elapsed timer (reuses chat_preview pattern).
On stop: saves metadata via RecordingStore.
"""

from __future__ import annotations

import math
import time
from enum import Enum, auto

import pygame

from device.display.theme import get_font
from device.display.tokens import DIM2, DIM3, HAIRLINE, WHITE
from device.ui.panels.base import PreviewPanel, ITEM_H, PAD_X, PAD_Y, FONT_SIZE
from device.recordings import RecordingStore, Recording


TITLE_FONT_SIZE = 10
TITLE_PAD_X = 6
TITLE_PAD_Y = 6
TITLE_H = 24


class FieldRecState(Enum):
    IDLE = auto()
    RECORDING = auto()
    SAVING = auto()
    DONE = auto()


# Static menu items (always present at top and bottom)
_MENU_ITEMS = [
    {"label": "NEW RECORDING", "description": "Start field recording", "action": "new_recording"},
    {"label": "BACK TO MAIN MENU", "description": "Return to sidebar", "action": "back"},
]


def _format_duration(seconds: float) -> str:
    """Format seconds as M:SS."""
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _format_time_ago(iso_str: str) -> str:
    """Rough human-readable time-ago from ISO timestamp."""
    try:
        from datetime import datetime, timezone
        recorded = datetime.fromisoformat(iso_str)
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - recorded
        mins = int(delta.total_seconds() / 60)
        if mins < 1:
            return "just now"
        if mins < 60:
            return f"{mins}m ago"
        hours = mins // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"
    except Exception:
        return ""


class FieldRecordingPanel(PreviewPanel):
    """Preview panel for RECORD sidebar item with field recording state machine."""

    def __init__(self, on_action: callable, recording_store: RecordingStore | None = None):
        items = [dict(item) for item in _MENU_ITEMS]
        super().__init__(items=items, on_action=on_action)
        self._store = recording_store or RecordingStore()
        self._state = FieldRecState.IDLE
        self._rec_start_time: float = 0.0
        self._saved_recording: Recording | None = None
        self._done_time: float = 0.0
        self._refresh_items()

    # ── Public API ──

    @property
    def state(self) -> FieldRecState:
        return self._state

    @property
    def elapsed(self) -> float:
        """Seconds elapsed since recording started (0 if not recording)."""
        if self._state == FieldRecState.RECORDING:
            return time.time() - self._rec_start_time
        return 0.0

    def set_store(self, store: RecordingStore) -> None:
        self._store = store
        self._refresh_items()

    # ── Item list management ──

    def _refresh_items(self) -> None:
        """Rebuild items list: NEW RECORDING + recent recordings + BACK."""
        items: list[dict] = [dict(_MENU_ITEMS[0])]

        # Insert recent recordings as navigable items
        try:
            recent = self._store.list_recent(limit=5)
        except Exception:
            recent = []

        for rec in recent:
            dur = _format_duration(rec.duration_s)
            ago = _format_time_ago(rec.recorded_at)
            label = f"{dur} recording"
            subtext = ago
            items.append({
                "label": label,
                "description": rec.id,
                "action": f"view_{rec.id}",
                "subtext": subtext,
            })

        items.append(dict(_MENU_ITEMS[1]))  # BACK
        self.items = items

    # ── Gesture routing ──

    def handle_action(self, action: str) -> bool:
        if self._state == FieldRecState.RECORDING:
            if action in ("SHORT_PRESS", "DOUBLE_PRESS"):
                self._stop_recording()
            elif action == "LONG_PRESS":
                self._cancel_recording()
            return True

        if self._state == FieldRecState.SAVING:
            return True  # swallow input while saving

        if self._state == FieldRecState.DONE:
            # Any press returns to IDLE
            self._state = FieldRecState.IDLE
            self._refresh_items()
            return True

        # IDLE state: check if NEW RECORDING is activated
        if action == "DOUBLE_PRESS" and self.selected_index >= 0:
            item = self.items[self.selected_index]
            if item.get("action") == "new_recording":
                self._start_recording()
                return True

        return super().handle_action(action)

    # ── Update loop ──

    def update(self, dt: float) -> None:
        # Auto-dismiss DONE after 2 seconds
        if self._state == FieldRecState.DONE:
            if time.time() - self._done_time > 2.0:
                self._state = FieldRecState.IDLE
                self._refresh_items()

    # ── Render ──

    def render(self, surface: pygame.Surface) -> None:
        w = surface.get_width()

        if self._state == FieldRecState.RECORDING:
            self._render_recording(surface, w)
        elif self._state == FieldRecState.SAVING:
            self._render_saving(surface)
        elif self._state == FieldRecState.DONE:
            self._render_done(surface)
        else:
            # IDLE: title + submenu items
            font = get_font(TITLE_FONT_SIZE)
            title_surf = font.render("RECORD", False, WHITE)
            surface.blit(title_surf, (TITLE_PAD_X, TITLE_PAD_Y))
            self._render_items(surface, y_offset=TITLE_H)

    def _render_recording(self, surface: pygame.Surface, w: int) -> None:
        """Full recording view: red dot + timer + hint."""
        font = get_font(FONT_SIZE)
        subtext_font = get_font(FONT_SIZE - 2)
        now = time.time()

        # Red-tinted background (1Hz breathe)
        bg_pulse = (math.sin(now * 1.0 * 2 * math.pi) + 1) / 2
        bg_r = int(25 + 30 * bg_pulse)
        pygame.draw.rect(surface, (bg_r, 5, 5), pygame.Rect(0, 0, w, ITEM_H * 3))

        # Pulsing red dot (2Hz)
        dot_pulse = (math.sin(now * 2.0 * 2 * math.pi) + 1) / 2
        dot_bright = int(140 + 115 * dot_pulse)
        dot_r = 4 + int(dot_pulse)
        center_y = ITEM_H + ITEM_H // 2
        pygame.draw.circle(surface, (dot_bright, 20, 20),
                           (PAD_X + 6, center_y), dot_r)

        # Timer
        elapsed = int(now - self._rec_start_time)
        mins, secs = divmod(elapsed, 60)
        timer_surf = font.render(f"REC {mins}:{secs:02d}", False, (220, 80, 80))
        surface.blit(timer_surf, (PAD_X + 14, center_y - timer_surf.get_height() // 2))

        # Hint
        hint = subtext_font.render("Click to stop  |  Hold to cancel", False, DIM3)
        surface.blit(hint, (PAD_X, ITEM_H * 3 + PAD_Y))

    def _render_saving(self, surface: pygame.Surface) -> None:
        font = get_font(FONT_SIZE)
        dot_count = int(time.time() * 3.75) % 4
        dots = "." * dot_count
        text_surf = font.render("SAVING" + dots, False, DIM2)
        surface.blit(text_surf, (PAD_X, TITLE_H))

    def _render_done(self, surface: pygame.Surface) -> None:
        font = get_font(FONT_SIZE)
        subtext_font = get_font(FONT_SIZE - 2)

        text_surf = font.render("SAVED", False, WHITE)
        surface.blit(text_surf, (PAD_X, TITLE_H))

        if self._saved_recording:
            dur = _format_duration(self._saved_recording.duration_s)
            detail = subtext_font.render(f"{dur} recorded", False, DIM3)
            surface.blit(detail, (PAD_X, TITLE_H + font.get_height() + 4))

    # ── Recording state machine ──

    def _start_recording(self) -> None:
        self._state = FieldRecState.RECORDING
        self._rec_start_time = time.time()
        self._saved_recording = None

    def _stop_recording(self) -> None:
        duration = time.time() - self._rec_start_time
        self._state = FieldRecState.SAVING

        # Save metadata
        try:
            rec = self._store.create(duration_s=round(duration, 1))
            self._saved_recording = rec
        except Exception:
            self._saved_recording = None

        self._state = FieldRecState.DONE
        self._done_time = time.time()
        self._refresh_items()

    def _cancel_recording(self) -> None:
        self._state = FieldRecState.IDLE
        self._saved_recording = None
        self._refresh_items()
