"""Notification coalescer — groups by coalesce_key with time-windowed batching.

Groups notifications from the same source (e.g. same SMS thread, same email
thread) and delivers them as a single item with a count, rather than flooding
the device with individual events.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .models import NotificationEvent, Priority


# ── Batch windows per priority ───────────────────────────────────────

BATCH_WINDOWS: dict[Priority, float] = {
    Priority.CRITICAL: 0.0,   # P1: immediate
    Priority.HIGH: 0.0,       # P2: immediate
    Priority.NORMAL: 30.0,    # P3: 30-second window
    Priority.LOW: 300.0,      # P4: 5-minute window
    Priority.SILENT: 600.0,   # P5: 10-minute window
}

# After this many messages in one coalesce group, collapse to count mode
THREAD_COLLAPSE_THRESHOLD = 4


@dataclass
class CoalesceGroup:
    """Tracks a group of notifications sharing a coalesce_key."""

    key: str
    events: list[NotificationEvent] = field(default_factory=list)
    first_ts: float = 0.0
    last_ts: float = 0.0
    delivered: bool = False

    @property
    def count(self) -> int:
        return len(self.events)

    @property
    def latest(self) -> NotificationEvent | None:
        return self.events[-1] if self.events else None

    def add(self, event: NotificationEvent) -> None:
        now = time.time()
        if not self.events:
            self.first_ts = now
        self.last_ts = now
        self.events.append(event)


def coalesce_key(event: NotificationEvent) -> str:
    """Generate coalesce key from category + source_id."""
    source_id = event.payload.get("source_id", "")
    return f"{event.category}:{source_id}"


class Coalescer:
    """Groups notifications by coalesce_key with time-windowed batching.

    Usage:
        coalescer = Coalescer(on_deliver=my_deliver_fn)
        coalescer.ingest(event)   # may deliver immediately or batch
        coalescer.flush()         # force-deliver all pending batches
        coalescer.tick()          # call periodically to flush expired windows
    """

    def __init__(self, on_deliver: Callable[[NotificationEvent, int], None] | None = None):
        """
        Args:
            on_deliver: Callback receiving (event, count) where event is the
                most recent in the group and count is how many were coalesced.
        """
        self._on_deliver = on_deliver
        self._groups: dict[str, CoalesceGroup] = {}

    @property
    def pending_groups(self) -> dict[str, CoalesceGroup]:
        """Read-only access to pending groups for inspection."""
        return dict(self._groups)

    def ingest(self, event: NotificationEvent) -> bool:
        """Ingest a notification event.

        Returns True if the event was delivered immediately.
        Returns False if it was batched for later delivery.
        """
        key = coalesce_key(event)
        window = BATCH_WINDOWS.get(event.priority, 30.0)

        # Immediate delivery for P1-P2
        if window == 0.0:
            group = self._groups.get(key)
            if group and not group.delivered:
                group.add(event)
                self._deliver_group(group)
                return True
            # Fresh group, deliver immediately
            group = CoalesceGroup(key=key)
            group.add(event)
            self._groups[key] = group
            self._deliver_group(group)
            return True

        # Batched delivery for P3+
        group = self._groups.get(key)
        if group is not None and not group.delivered:
            group.add(event)
            # Thread collapse: if we exceed threshold, deliver a summary now
            if group.count >= THREAD_COLLAPSE_THRESHOLD:
                self._deliver_group(group)
                return True
            return False

        # New batch group
        group = CoalesceGroup(key=key)
        group.add(event)
        self._groups[key] = group
        return False

    def tick(self) -> int:
        """Check all pending groups and deliver those whose batch window expired.

        Call this periodically (e.g. every second). Returns count of groups delivered.
        """
        now = time.time()
        delivered = 0
        for key, group in list(self._groups.items()):
            if group.delivered:
                continue
            if not group.events:
                continue
            window = BATCH_WINDOWS.get(group.events[0].priority, 30.0)
            if window == 0.0:
                continue  # immediate events already handled
            elapsed = now - group.first_ts
            if elapsed >= window:
                self._deliver_group(group)
                delivered += 1
        return delivered

    def flush(self) -> int:
        """Force-deliver all pending groups. Returns count delivered."""
        delivered = 0
        for group in self._groups.values():
            if not group.delivered and group.events:
                self._deliver_group(group)
                delivered += 1
        return delivered

    def clear(self) -> None:
        """Remove all groups (delivered and pending)."""
        self._groups.clear()

    def _deliver_group(self, group: CoalesceGroup) -> None:
        """Mark group as delivered and fire callback."""
        group.delivered = True
        if self._on_deliver and group.latest:
            self._on_deliver(group.latest, group.count)
