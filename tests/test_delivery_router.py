"""Tests for the delivery router — full notification pipeline."""
from __future__ import annotations

import time

import pytest

from server.notifications.models import NotificationEvent, Priority
from server.notifications.priority import FocusMode, PriorityClassifier
from server.notifications.router import (
    DeliveryAction,
    DeliveryRouter,
    Modality,
    EARCON_COOLDOWN_S,
)


def _evt(
    category: str = "sms",
    source_id: str = "src1",
    body: str = "hello",
    sender: str = "",
    sub_type: str = "",
    priority: Priority = Priority.NORMAL,
) -> NotificationEvent:
    payload = {"body": body, "source_id": source_id}
    if sender:
        payload["sender"] = sender
    if sub_type:
        payload["sub_type"] = sub_type
    return NotificationEvent(
        type="notification",
        priority=priority,
        category=category,
        payload=payload,
    )


# ── Basic routing by priority ───────────────────────────────────────


class TestModalityRouting:
    def test_p1_gets_full_screen(self):
        actions = []
        r = DeliveryRouter(on_delivery=actions.append)
        r.ingest(_evt(category="reminder"))  # CRITICAL
        assert len(actions) == 1
        assert actions[0].modality == Modality.FULL_SCREEN

    def test_p2_gets_banner(self):
        actions = []
        r = DeliveryRouter(on_delivery=actions.append)
        r.ingest(_evt(category="sms"))  # HIGH
        assert len(actions) == 1
        assert actions[0].modality == Modality.BANNER

    def test_p3_batched_then_toast(self):
        actions = []
        r = DeliveryRouter(on_delivery=actions.append)
        r.ingest(_evt(category="mail"))  # NORMAL
        # Not delivered yet (batched)
        assert len(actions) == 0
        # Force flush
        r._coalescer.flush()
        assert len(actions) == 1
        assert actions[0].modality == Modality.TOAST

    def test_p4_batched_then_badge(self):
        actions = []
        r = DeliveryRouter(on_delivery=actions.append)
        r.ingest(_evt(category="system"))  # LOW
        r._coalescer.flush()
        assert len(actions) == 1
        assert actions[0].modality == Modality.BADGE


# ── Earcon / TTS / Wake ─────────────────────────────────────────────


class TestDeliveryFlags:
    def test_p1_has_tts_and_earcon_and_wake(self):
        actions = []
        r = DeliveryRouter(on_delivery=actions.append)
        r.ingest(_evt(category="reminder", body="test", sender="Mom"))
        action = actions[0]
        assert action.play_earcon is True
        assert action.wake_screen is True
        assert "Mom" in action.tts_text
        assert "test" in action.tts_text

    def test_p2_has_earcon_and_wake(self):
        actions = []
        r = DeliveryRouter(on_delivery=actions.append)
        r.ingest(_evt(category="sms"))
        action = actions[0]
        assert action.play_earcon is True
        assert action.wake_screen is True

    def test_p3_has_no_earcon(self):
        actions = []
        r = DeliveryRouter(on_delivery=actions.append)
        r.ingest(_evt(category="mail"))
        r._coalescer.flush()
        action = actions[0]
        assert action.play_earcon is False
        assert action.wake_screen is False

    def test_earcon_cooldown(self):
        actions = []
        r = DeliveryRouter(on_delivery=actions.append)
        # First P2 gets earcon
        r.ingest(_evt(category="sms", source_id="a"))
        assert actions[0].play_earcon is True
        # Immediate second P2 should NOT get earcon (cooldown)
        r.ingest(_evt(category="sms", source_id="b"))
        assert actions[1].play_earcon is False


# ── DND queue ────────────────────────────────────────────────────────


class TestDNDQueue:
    def test_dnd_queues_non_critical(self):
        actions = []
        r = DeliveryRouter(on_delivery=actions.append)
        r.focus_mode = FocusMode.DO_NOT_DISTURB
        r.ingest(_evt(category="mail"))
        assert len(actions) == 0
        assert r.dnd_queue_size == 1

    def test_dnd_allows_critical(self):
        actions = []
        r = DeliveryRouter(on_delivery=actions.append)
        r.focus_mode = FocusMode.DO_NOT_DISTURB
        r.ingest(_evt(category="reminder"))  # CRITICAL
        assert len(actions) == 1

    def test_flush_dnd_individual(self):
        actions = []
        r = DeliveryRouter(on_delivery=actions.append)
        r.focus_mode = FocusMode.DO_NOT_DISTURB
        for i in range(3):
            r.ingest(_evt(category="sms", source_id=f"s{i}"))
        assert len(actions) == 0

        r.focus_mode = FocusMode.NORMAL
        count = r.flush_dnd_queue()
        assert count == 3
        assert len(actions) == 3

    def test_flush_dnd_summary_when_large(self):
        actions = []
        r = DeliveryRouter(on_delivery=actions.append)
        r.focus_mode = FocusMode.DO_NOT_DISTURB
        for i in range(7):
            r.ingest(_evt(category="mail", source_id=f"s{i}"))

        r.focus_mode = FocusMode.NORMAL
        count = r.flush_dnd_queue()
        assert count == 7
        # Should get a single summary toast
        assert len(actions) == 1
        assert actions[0].modality == Modality.TOAST
        assert actions[0].count == 7

    def test_flush_empty_queue_returns_zero(self):
        r = DeliveryRouter()
        assert r.flush_dnd_queue() == 0

    def test_dnd_queue_cleared_after_flush(self):
        r = DeliveryRouter()
        r.focus_mode = FocusMode.DO_NOT_DISTURB
        r.ingest(_evt(category="mail"))
        r.focus_mode = FocusMode.NORMAL
        r.flush_dnd_queue()
        assert r.dnd_queue_size == 0


# ── Stats ────────────────────────────────────────────────────────────


class TestStats:
    def test_ingestion_counted(self):
        r = DeliveryRouter()
        r.ingest(_evt(category="sms"))
        assert r.stats.total_ingested == 1

    def test_dnd_queued_counted(self):
        r = DeliveryRouter()
        r.focus_mode = FocusMode.DO_NOT_DISTURB
        r.ingest(_evt(category="mail"))
        assert r.stats.dnd_queued == 1

    def test_delivered_counted(self):
        r = DeliveryRouter()
        r.ingest(_evt(category="sms"))  # immediate P2
        assert r.stats.total_delivered == 1


# ── Classifier proxy ────────────────────────────────────────────────


class TestClassifierProxy:
    def test_focus_mode_property(self):
        r = DeliveryRouter()
        assert r.focus_mode == FocusMode.NORMAL
        r.focus_mode = FocusMode.SLEEP
        assert r.focus_mode == FocusMode.SLEEP

    def test_classifier_accessible(self):
        c = PriorityClassifier(vip_contacts=["Mom"])
        r = DeliveryRouter(classifier=c)
        assert r.classifier.vip_contacts == ["Mom"]


# ── Tick ─────────────────────────────────────────────────────────────


class TestTick:
    def test_tick_returns_zero_when_nothing_pending(self):
        r = DeliveryRouter()
        assert r.tick() == 0

    def test_tick_flushes_expired_batches(self):
        actions = []
        r = DeliveryRouter(on_delivery=actions.append)
        r.ingest(_evt(category="mail"))  # P3, batched

        # Simulate time passing
        for group in r._coalescer.pending_groups.values():
            group.first_ts = time.time() - 60

        count = r.tick()
        assert count == 1
        assert len(actions) == 1
