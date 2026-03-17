"""Central notification dispatcher with dedup and persistent queue."""
from __future__ import annotations

import time
from typing import Callable

from .models import NotificationEvent
from .queue_store import QueueStore

Callback = Callable[[NotificationEvent], None]


class NotificationDispatcher:
    """Deduplicates, persists, and fans-out notification events."""

    def __init__(self, store: QueueStore, dedup_window: float = 60.0):
        self._store = store
        self._dedup_window = dedup_window
        self._callbacks: list[Callback] = []
        # dedup_key -> timestamp of last dispatch
        self._seen: dict[str, float] = {}

    # ------------------------------------------------------------------
    def register_callback(self, cb: Callback) -> None:
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def unregister_callback(self, cb: Callback) -> None:
        try:
            self._callbacks.remove(cb)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    def dispatch(self, event: NotificationEvent) -> bool:
        """Dispatch an event. Returns True if delivered (not deduped)."""
        now = time.time()

        # --- dedup check ---
        key = event.dedup_key
        last_seen = self._seen.get(key)
        if last_seen is not None and (now - last_seen) < self._dedup_window:
            return False

        self._seen[key] = now

        # --- persist ---
        self._store.push(event)

        # --- fan-out ---
        for cb in self._callbacks:
            cb(event)

        return True
