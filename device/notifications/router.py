"""NotificationRouter — DND-aware event routing by priority tier."""
from __future__ import annotations

from typing import Callable


class NotificationRouter:
    """Route notification events to banner, toast, or badge by priority.

    Priority tiers:
        P1 (critical)  → banner, always breaks through DND
        P2 (high)      → banner, queued during DND
        P3 (normal)    → toast, queued during DND
        P4-P5 (low)    → badge only, queued during DND
    """

    COALESCE_THRESHOLD = 5

    def __init__(
        self,
        on_banner: Callable[[dict], None],
        on_toast: Callable[[dict], None],
        on_badge: Callable[[int], None] | None = None,
    ):
        self._on_banner = on_banner
        self._on_toast = on_toast
        self._on_badge = on_badge
        self._dnd_active = False
        self._dnd_reason = ""
        self._queue: list[dict] = []
        self._unread_count = 0

    # ------------------------------------------------------------------
    # DND management
    # ------------------------------------------------------------------

    def set_dnd(self, active: bool, reason: str = "") -> None:
        """Enable or disable Do Not Disturb.

        When active, P2+ events are queued silently.
        P1 always breaks through.
        When deactivated, the queued events are drained.
        """
        self._dnd_active = active
        self._dnd_reason = reason
        if not active:
            self._drain_queue()

    # ------------------------------------------------------------------
    # Event ingestion
    # ------------------------------------------------------------------

    def on_event(self, event: dict) -> None:
        """Route an incoming notification event by priority."""
        priority = event.get("priority", 3)

        if self._dnd_active and priority != 1:
            self._queue.append(event)
            self._unread_count += 1
            self._notify_badge()
            return

        self._deliver(event)

    # ------------------------------------------------------------------
    # Internal delivery
    # ------------------------------------------------------------------

    def _deliver(self, event: dict) -> None:
        """Deliver a single event to the correct output."""
        priority = event.get("priority", 3)
        self._unread_count += 1
        self._notify_badge()

        if priority <= 2:
            self._on_banner(event)
        elif priority == 3:
            self._on_toast(event)
        # P4-P5: badge only (already incremented above)

    def _drain_queue(self) -> None:
        """Flush the DND queue.

        If more than COALESCE_THRESHOLD items, deliver a single summary
        toast instead of individual notifications.
        """
        if not self._queue:
            return

        if len(self._queue) > self.COALESCE_THRESHOLD:
            summary = {
                "app": "system",
                "title": "Notifications",
                "message": f"{len(self._queue)} notifications while DND was active",
                "priority": 3,
                "coalesced": True,
                "count": len(self._queue),
            }
            self._on_toast(summary)
        else:
            # Sort by priority (ascending = most urgent first), then by time
            sorted_q = sorted(
                self._queue,
                key=lambda e: (e.get("priority", 3), e.get("time", "")),
            )
            for event in sorted_q:
                self._deliver_without_badge(event)

        self._queue.clear()

    def _deliver_without_badge(self, event: dict) -> None:
        """Deliver without incrementing badge (already counted on queue)."""
        priority = event.get("priority", 3)
        if priority <= 2:
            self._on_banner(event)
        elif priority == 3:
            self._on_toast(event)

    def _notify_badge(self) -> None:
        if self._on_badge:
            self._on_badge(self._unread_count)

    # ------------------------------------------------------------------
    # Badge
    # ------------------------------------------------------------------

    def clear_unread(self) -> None:
        """Reset the unread counter and notify badge."""
        self._unread_count = 0
        self._notify_badge()

    @property
    def unread_count(self) -> int:
        return self._unread_count

    @property
    def dnd_active(self) -> bool:
        return self._dnd_active
