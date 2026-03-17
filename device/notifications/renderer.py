"""Device-side notification renderer — dispatches delivery actions to UI.

Receives delivery action dicts from the server (via WebSocket) and renders
them as toast, banner, badge, or full-screen takeover on the device OLED.

Integrates with the existing NotificationRouter and overlay system.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

logger = logging.getLogger(__name__)


# ── Modality constants (mirror server/notifications/router.py) ───────

MODALITY_FULL_SCREEN = "full_screen"
MODALITY_BANNER = "banner"
MODALITY_TOAST = "toast"
MODALITY_BADGE = "badge"
MODALITY_SILENT = "silent"
MODALITY_QUEUED = "queued"

# Auto-dismiss durations by modality
DISMISS_MS = {
    MODALITY_TOAST: 3000,
    MODALITY_BANNER: 15000,
    MODALITY_FULL_SCREEN: 0,  # manual dismiss only
}


@dataclass
class RenderedNotification:
    """A notification ready for display on the device."""

    event_id: str
    modality: str
    title: str
    body: str
    category: str = "system"
    count: int = 1
    play_earcon: bool = False
    tts_text: str = ""
    wake_screen: bool = False
    timestamp: float = field(default_factory=time.time)


class DisplayCallbacks(Protocol):
    """Protocol for display integration callbacks."""

    def show_toast(self, title: str, body: str, category: str, duration_ms: int) -> None: ...
    def show_banner(self, title: str, body: str, category: str, duration_ms: int) -> None: ...
    def show_full_screen(self, title: str, body: str, category: str) -> None: ...
    def update_badge(self, count: int) -> None: ...
    def wake_screen(self) -> None: ...


class NotificationRenderer:
    """Renders incoming delivery actions on the device display.

    Connects to the existing notification WebSocket client and translates
    server-side DeliveryAction dicts into device UI primitives.
    """

    def __init__(
        self,
        on_toast: Callable[[str, str, str, int], None] | None = None,
        on_banner: Callable[[str, str, str, int], None] | None = None,
        on_full_screen: Callable[[str, str, str], None] | None = None,
        on_badge: Callable[[int], None] | None = None,
        on_wake: Callable[[], None] | None = None,
        on_tts: Callable[[str], None] | None = None,
        on_earcon: Callable[[str], None] | None = None,
    ):
        self._on_toast = on_toast
        self._on_banner = on_banner
        self._on_full_screen = on_full_screen
        self._on_badge = on_badge
        self._on_wake = on_wake
        self._on_tts = on_tts
        self._on_earcon = on_earcon
        self._badge_count = 0
        self._history: list[RenderedNotification] = []
        self._max_history = 50

    @property
    def badge_count(self) -> int:
        return self._badge_count

    @property
    def history(self) -> list[RenderedNotification]:
        return list(self._history)

    def clear_badge(self) -> None:
        """Reset badge counter to zero."""
        self._badge_count = 0
        if self._on_badge:
            self._on_badge(0)

    def handle_delivery(self, data: dict) -> RenderedNotification | None:
        """Process a delivery action dict from the server WebSocket.

        Expected keys in data:
            event: dict with id, category, payload (title, body, sender, ...)
            modality: str (full_screen, banner, toast, badge, silent)
            count: int (coalesced count)
            play_earcon: bool
            tts_text: str
            wake_screen: bool

        Returns the RenderedNotification if rendered, None if silent.
        """
        event = data.get("event", {})
        modality = data.get("modality", MODALITY_TOAST)
        count = data.get("count", 1)
        play_earcon = data.get("play_earcon", False)
        tts_text = data.get("tts_text", "")
        wake_screen = data.get("wake_screen", False)

        payload = event.get("payload", {})
        title = payload.get("title", payload.get("app", ""))
        body = payload.get("body", "")
        category = event.get("category", "system")
        event_id = event.get("id", "")

        # Build count-aware body
        if count > 1:
            body = f"({count}) {body}"

        rendered = RenderedNotification(
            event_id=event_id,
            modality=modality,
            title=title,
            body=body,
            category=category,
            count=count,
            play_earcon=play_earcon,
            tts_text=tts_text,
            wake_screen=wake_screen,
        )

        self._add_history(rendered)

        # Wake screen if needed
        if wake_screen and self._on_wake:
            self._on_wake()

        # Play earcon
        if play_earcon and self._on_earcon:
            self._on_earcon(category)

        # Route to correct display
        if modality == MODALITY_FULL_SCREEN:
            self._badge_count += 1
            self._notify_badge()
            if self._on_full_screen:
                self._on_full_screen(title, body, category)
            # TTS for full-screen takeover
            if tts_text and self._on_tts:
                self._on_tts(tts_text)

        elif modality == MODALITY_BANNER:
            self._badge_count += 1
            self._notify_badge()
            duration = DISMISS_MS.get(MODALITY_BANNER, 15000)
            if self._on_banner:
                self._on_banner(title, body, category, duration)

        elif modality == MODALITY_TOAST:
            self._badge_count += 1
            self._notify_badge()
            duration = DISMISS_MS.get(MODALITY_TOAST, 3000)
            if self._on_toast:
                self._on_toast(title, body, category, duration)

        elif modality == MODALITY_BADGE:
            self._badge_count += 1
            self._notify_badge()

        elif modality == MODALITY_SILENT:
            # No visible delivery, just track
            pass

        else:
            logger.warning("Unknown modality: %s", modality)
            return None

        return rendered

    def _notify_badge(self) -> None:
        if self._on_badge:
            self._on_badge(self._badge_count)

    def _add_history(self, notification: RenderedNotification) -> None:
        self._history.append(notification)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
