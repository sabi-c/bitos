"""Tests for the notification coalescer — time-windowed grouping."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from server.notifications.models import NotificationEvent, Priority
from server.notifications.coalescer import (
    Coalescer,
    CoalesceGroup,
    coalesce_key,
    BATCH_WINDOWS,
    THREAD_COLLAPSE_THRESHOLD,
)


def _evt(
    category: str = "sms",
    source_id: str = "thread1",
    body: str = "hello",
    priority: Priority = Priority.NORMAL,
) -> NotificationEvent:
    return NotificationEvent(
        type="notification",
        priority=priority,
        category=category,
        payload={"body": body, "source_id": source_id},
    )


# ── coalesce_key ─────────────────────────────────────────────────────


class TestCoalesceKey:
    def test_basic_key(self):
        evt = _evt(category="sms", source_id="chat_123")
        assert coalesce_key(evt) == "sms:chat_123"

    def test_empty_source_id(self):
        evt = _evt(category="mail", source_id="")
        assert coalesce_key(evt) == "mail:"

    def test_different_categories_different_keys(self):
        e1 = _evt(category="sms", source_id="x")
        e2 = _evt(category="mail", source_id="x")
        assert coalesce_key(e1) != coalesce_key(e2)


# ── CoalesceGroup ────────────────────────────────────────────────────


class TestCoalesceGroup:
    def test_empty_group(self):
        g = CoalesceGroup(key="sms:x")
        assert g.count == 0
        assert g.latest is None

    def test_add_events(self):
        g = CoalesceGroup(key="sms:x")
        e1 = _evt()
        e2 = _evt(body="world")
        g.add(e1)
        g.add(e2)
        assert g.count == 2
        assert g.latest is e2
        assert g.first_ts > 0
        assert g.last_ts >= g.first_ts


# ── Immediate delivery (P1-P2) ──────────────────────────────────────


class TestImmediateDelivery:
    def test_p1_delivers_immediately(self):
        delivered = []
        c = Coalescer(on_deliver=lambda e, n: delivered.append((e, n)))

        evt = _evt(priority=Priority.CRITICAL)
        result = c.ingest(evt)

        assert result is True
        assert len(delivered) == 1
        assert delivered[0] == (evt, 1)

    def test_p2_delivers_immediately(self):
        delivered = []
        c = Coalescer(on_deliver=lambda e, n: delivered.append((e, n)))

        evt = _evt(priority=Priority.HIGH)
        result = c.ingest(evt)

        assert result is True
        assert len(delivered) == 1

    def test_p1_coalesces_with_existing_group(self):
        delivered = []
        c = Coalescer(on_deliver=lambda e, n: delivered.append((e, n)))

        e1 = _evt(priority=Priority.CRITICAL, source_id="x")
        e2 = _evt(priority=Priority.CRITICAL, source_id="x", body="follow up")

        c.ingest(e1)
        # Reset delivered state by ingesting second event to same key
        # The group was already delivered, so e2 creates a new one
        c.ingest(e2)

        assert len(delivered) == 2


# ── Batched delivery (P3+) ──────────────────────────────────────────


class TestBatchedDelivery:
    def test_p3_is_batched(self):
        delivered = []
        c = Coalescer(on_deliver=lambda e, n: delivered.append((e, n)))

        evt = _evt(priority=Priority.NORMAL)
        result = c.ingest(evt)

        assert result is False
        assert len(delivered) == 0

    def test_p4_is_batched(self):
        delivered = []
        c = Coalescer(on_deliver=lambda e, n: delivered.append((e, n)))

        evt = _evt(priority=Priority.LOW)
        result = c.ingest(evt)

        assert result is False
        assert len(delivered) == 0

    def test_same_key_coalesces(self):
        delivered = []
        c = Coalescer(on_deliver=lambda e, n: delivered.append((e, n)))

        for i in range(3):
            c.ingest(_evt(priority=Priority.NORMAL, source_id="t1", body=f"msg{i}"))

        assert len(delivered) == 0
        assert "sms:t1" in c.pending_groups
        assert c.pending_groups["sms:t1"].count == 3

    def test_different_keys_separate_groups(self):
        delivered = []
        c = Coalescer(on_deliver=lambda e, n: delivered.append((e, n)))

        c.ingest(_evt(priority=Priority.NORMAL, source_id="t1"))
        c.ingest(_evt(priority=Priority.NORMAL, source_id="t2"))

        assert len(c.pending_groups) == 2

    def test_thread_collapse_at_threshold(self):
        delivered = []
        c = Coalescer(on_deliver=lambda e, n: delivered.append((e, n)))

        for i in range(THREAD_COLLAPSE_THRESHOLD):
            c.ingest(_evt(priority=Priority.NORMAL, source_id="t1", body=f"msg{i}"))

        # Should have triggered collapse delivery
        assert len(delivered) == 1
        evt, count = delivered[0]
        assert count == THREAD_COLLAPSE_THRESHOLD
        assert evt.payload["body"] == f"msg{THREAD_COLLAPSE_THRESHOLD - 1}"


# ── tick() — time-based flush ────────────────────────────────────────


class TestTick:
    def test_tick_delivers_expired_groups(self):
        delivered = []
        c = Coalescer(on_deliver=lambda e, n: delivered.append((e, n)))

        # Ingest a P3 event
        c.ingest(_evt(priority=Priority.NORMAL, source_id="t1"))
        assert len(delivered) == 0

        # Simulate time passing beyond the batch window
        group = c.pending_groups["sms:t1"]
        group.first_ts = time.time() - 60  # 60s ago, window is 30s

        count = c.tick()
        assert count == 1
        assert len(delivered) == 1

    def test_tick_skips_immediate_groups(self):
        delivered = []
        c = Coalescer(on_deliver=lambda e, n: delivered.append((e, n)))

        c.ingest(_evt(priority=Priority.CRITICAL))
        delivered.clear()

        count = c.tick()
        assert count == 0

    def test_tick_skips_already_delivered(self):
        delivered = []
        c = Coalescer(on_deliver=lambda e, n: delivered.append((e, n)))

        c.ingest(_evt(priority=Priority.NORMAL))
        c.flush()
        delivered.clear()

        count = c.tick()
        assert count == 0


# ── flush() ──────────────────────────────────────────────────────────


class TestFlush:
    def test_flush_delivers_all_pending(self):
        delivered = []
        c = Coalescer(on_deliver=lambda e, n: delivered.append((e, n)))

        c.ingest(_evt(priority=Priority.NORMAL, source_id="t1"))
        c.ingest(_evt(priority=Priority.NORMAL, source_id="t2"))

        count = c.flush()
        assert count == 2
        assert len(delivered) == 2

    def test_flush_returns_zero_when_empty(self):
        c = Coalescer()
        assert c.flush() == 0

    def test_flush_returns_zero_when_all_delivered(self):
        delivered = []
        c = Coalescer(on_deliver=lambda e, n: delivered.append((e, n)))

        c.ingest(_evt(priority=Priority.CRITICAL))
        assert c.flush() == 0  # already delivered immediately


# ── clear() ──────────────────────────────────────────────────────────


class TestClear:
    def test_clear_removes_all_groups(self):
        c = Coalescer()
        c.ingest(_evt(priority=Priority.NORMAL))
        c.ingest(_evt(priority=Priority.CRITICAL))
        assert len(c.pending_groups) > 0
        c.clear()
        assert len(c.pending_groups) == 0


# ── No callback ──────────────────────────────────────────────────────


class TestNoCallback:
    def test_ingest_without_callback_doesnt_crash(self):
        c = Coalescer(on_deliver=None)
        c.ingest(_evt(priority=Priority.CRITICAL))
        c.ingest(_evt(priority=Priority.NORMAL))
        c.flush()
        # Should not raise
