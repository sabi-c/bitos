"""Tests for the server-side notification dispatcher."""
from __future__ import annotations

import time

import pytest

from server.notifications.models import NotificationEvent, Priority
from server.notifications.queue_store import QueueStore
from server.notifications.dispatcher import NotificationDispatcher


def _make_event(body: str = "hello", source_id: str = "src1",
                category: str = "sms", **kw) -> NotificationEvent:
    return NotificationEvent(
        type="notification",
        priority=kw.pop("priority", Priority.NORMAL),
        category=category,
        payload={"body": body, "source_id": source_id, **kw},
    )


@pytest.fixture
def store():
    s = QueueStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def dispatcher(store):
    return NotificationDispatcher(store, dedup_window=60.0)


# 1 ── dispatch stores and delivers ──────────────────────────────────
def test_dispatch_stores_and_delivers(dispatcher, store):
    delivered = []
    dispatcher.register_callback(delivered.append)

    evt = _make_event()
    assert dispatcher.dispatch(evt) is True
    assert len(delivered) == 1
    assert delivered[0].id == evt.id

    pending = store.get_pending()
    assert len(pending) == 1
    assert pending[0].id == evt.id


# 2 ── dedup within window ───────────────────────────────────────────
def test_dedup_within_window(dispatcher, store):
    delivered = []
    dispatcher.register_callback(delivered.append)

    evt1 = _make_event(body="same", source_id="x")
    evt2 = _make_event(body="same", source_id="x")

    assert dispatcher.dispatch(evt1) is True
    assert dispatcher.dispatch(evt2) is False
    assert len(delivered) == 1
    # only one row in the store
    assert len(store.get_pending()) == 1


# 3 ── different body not deduped ────────────────────────────────────
def test_different_body_not_deduped(dispatcher):
    delivered = []
    dispatcher.register_callback(delivered.append)

    assert dispatcher.dispatch(_make_event(body="aaa")) is True
    assert dispatcher.dispatch(_make_event(body="bbb")) is True
    assert len(delivered) == 2


# 4 ── ack marks delivered ───────────────────────────────────────────
def test_ack_marks_delivered(dispatcher, store):
    evt = _make_event()
    dispatcher.dispatch(evt)
    assert len(store.get_pending()) == 1

    store.mark_delivered(evt.id)
    assert len(store.get_pending()) == 0


# 5 ── get_since replays missed ──────────────────────────────────────
def test_get_since_replays(dispatcher, store):
    before = time.time() - 1
    evt = _make_event()
    dispatcher.dispatch(evt)
    store.mark_delivered(evt.id)

    # even though delivered, get_since should return it
    replayed = store.get_since(before)
    assert len(replayed) == 1
    assert replayed[0].id == evt.id


# 6 ── persist and retrieve ──────────────────────────────────────────
def test_persist_and_retrieve(store):
    evt = _make_event(body="persist me", priority=Priority.HIGH)
    store.push(evt)

    pending = store.get_pending()
    assert len(pending) == 1
    assert pending[0].payload["body"] == "persist me"
    assert pending[0].priority == Priority.HIGH
    assert pending[0].id == evt.id


# 7 ── expire old events ────────────────────────────────────────────
def test_expire_old_events(store):
    old_evt = _make_event(body="old")
    old_evt.timestamp = time.time() - 7200  # 2 hours ago
    store.push(old_evt)
    store.mark_delivered(old_evt.id)

    new_evt = _make_event(body="new")
    store.push(new_evt)
    store.mark_delivered(new_evt.id)

    deleted = store.expire_older_than_hours(1)
    assert deleted == 1
    # new_evt should still be there
    remaining = store.get_since(0)
    assert len(remaining) == 1
    assert remaining[0].id == new_evt.id
