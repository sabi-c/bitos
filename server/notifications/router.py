"""Delivery router — routes classified notifications to appropriate modalities.

Combines priority classification, coalescing, and focus-mode filtering into
a single pipeline: Ingest -> Classify -> Coalesce -> Filter -> Deliver.

Delivery modalities by priority:
    P1 CRITICAL: full-screen takeover + TTS + earcon
    P2 HIGH:     banner + earcon
    P3 NORMAL:   toast notification
    P4 LOW:      badge only / ambient blob glow
    P5 SILENT:   queue only (no visible delivery)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .models import NotificationEvent, Priority
from .priority import FocusMode, PriorityClassifier
from .coalescer import Coalescer, coalesce_key


class Modality(str, Enum):
    FULL_SCREEN = "full_screen"   # P1: takeover + TTS + earcon
    BANNER = "banner"             # P2: persistent banner + earcon
    TOAST = "toast"               # P3: auto-dismiss toast
    BADGE = "badge"               # P4: badge counter + ambient glow
    SILENT = "silent"             # P5: queue only
    QUEUED = "queued"             # held during DND


@dataclass
class DeliveryAction:
    """Describes how a notification should be delivered to the device."""

    event: NotificationEvent
    modality: Modality
    count: int = 1                # coalesced count
    play_earcon: bool = False
    tts_text: str = ""            # non-empty → read aloud
    wake_screen: bool = False


# Rate limit: max 1 earcon per this many seconds during burst
EARCON_COOLDOWN_S = 10.0


class DeliveryRouter:
    """Full notification pipeline: classify, coalesce, filter, route.

    Usage:
        router = DeliveryRouter(on_delivery=my_handler)
        router.ingest(event)      # runs full pipeline
        router.tick()             # call every ~1s for coalescer batching
        router.flush_dnd_queue()  # drain queued events after DND ends
    """

    def __init__(
        self,
        on_delivery: Callable[[DeliveryAction], None] | None = None,
        classifier: PriorityClassifier | None = None,
    ):
        self._on_delivery = on_delivery
        self._classifier = classifier or PriorityClassifier()
        self._coalescer = Coalescer(on_deliver=self._on_coalesced)
        self._dnd_queue: list[tuple[NotificationEvent, Priority]] = []
        self._last_earcon_ts: float = 0.0
        self._stats = _RouterStats()

    # ── Configuration proxies ────────────────────────────────────────

    @property
    def classifier(self) -> PriorityClassifier:
        return self._classifier

    @property
    def focus_mode(self) -> FocusMode:
        return self._classifier.focus_mode

    @focus_mode.setter
    def focus_mode(self, mode: FocusMode) -> None:
        self._classifier.focus_mode = mode

    @property
    def stats(self) -> _RouterStats:
        return self._stats

    # ── Main pipeline ────────────────────────────────────────────────

    def ingest(self, event: NotificationEvent) -> None:
        """Run full pipeline: classify -> filter -> coalesce -> deliver."""
        priority, should_deliver = self._classifier.classify_and_filter(event)
        event.priority = priority
        self._stats.total_ingested += 1

        if not should_deliver:
            self._dnd_queue.append((event, priority))
            self._stats.dnd_queued += 1
            return

        self._coalescer.ingest(event)

    def tick(self) -> int:
        """Flush expired coalescer batch windows. Call every ~1s."""
        return self._coalescer.tick()

    def flush_dnd_queue(self) -> int:
        """Drain the DND queue, delivering held notifications.

        Called when focus mode changes back to NORMAL.
        Delivers a summary if more than 5 items queued, otherwise individually.
        Returns count of events delivered.
        """
        if not self._dnd_queue:
            return 0

        count = len(self._dnd_queue)
        self._stats.dnd_drained += count

        if count > 5:
            # Deliver a summary instead of individual events
            summary_event = NotificationEvent(
                type="notification",
                priority=Priority.NORMAL,
                category="system",
                payload={
                    "title": "Notifications",
                    "body": f"{count} notifications while DND was active",
                    "app": "System",
                    "coalesced": True,
                    "count": count,
                },
            )
            action = DeliveryAction(
                event=summary_event,
                modality=Modality.TOAST,
                count=count,
            )
            self._emit(action)
        else:
            # Sort by priority (most urgent first), then timestamp
            sorted_q = sorted(self._dnd_queue, key=lambda t: (t[1], t[0].timestamp))
            for event, priority in sorted_q:
                action = self._build_action(event, priority, count=1)
                self._emit(action)

        self._dnd_queue.clear()
        return count

    @property
    def dnd_queue_size(self) -> int:
        return len(self._dnd_queue)

    # ── Coalescer callback ───────────────────────────────────────────

    def _on_coalesced(self, event: NotificationEvent, count: int) -> None:
        """Called by coalescer when a group is ready for delivery."""
        action = self._build_action(event, event.priority, count)
        self._stats.total_delivered += 1
        self._emit(action)

    # ── Action building ──────────────────────────────────────────────

    def _build_action(self, event: NotificationEvent, priority: Priority, count: int) -> DeliveryAction:
        """Map priority to delivery modality and flags."""
        now = time.time()
        can_earcon = (now - self._last_earcon_ts) >= EARCON_COOLDOWN_S

        if priority == Priority.CRITICAL:
            tts_body = event.payload.get("body", "")
            sender = event.payload.get("sender", event.payload.get("title", ""))
            tts_text = f"From {sender}: {tts_body}" if sender else tts_body
            if can_earcon:
                self._last_earcon_ts = now
            return DeliveryAction(
                event=event,
                modality=Modality.FULL_SCREEN,
                count=count,
                play_earcon=True,   # always for P1
                tts_text=tts_text,
                wake_screen=True,
            )

        if priority == Priority.HIGH:
            earcon = can_earcon
            if earcon:
                self._last_earcon_ts = now
            return DeliveryAction(
                event=event,
                modality=Modality.BANNER,
                count=count,
                play_earcon=earcon,
                wake_screen=True,
            )

        if priority == Priority.NORMAL:
            return DeliveryAction(
                event=event,
                modality=Modality.TOAST,
                count=count,
            )

        if priority == Priority.LOW:
            return DeliveryAction(
                event=event,
                modality=Modality.BADGE,
                count=count,
            )

        # P5 SILENT
        return DeliveryAction(
            event=event,
            modality=Modality.SILENT,
            count=count,
        )

    def _emit(self, action: DeliveryAction) -> None:
        if self._on_delivery:
            self._on_delivery(action)


@dataclass
class _RouterStats:
    """Counters for monitoring the delivery pipeline."""

    total_ingested: int = 0
    total_delivered: int = 0
    dnd_queued: int = 0
    dnd_drained: int = 0
