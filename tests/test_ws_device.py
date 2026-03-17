"""Tests for the DeviceWSHandler WebSocket notification handler."""
import time
from unittest.mock import MagicMock

from server.notifications.models import NotificationEvent, Priority
from server.notifications.queue_store import QueueStore
from server.notifications.dispatcher import NotificationDispatcher
from server.notifications.ws_handler import DeviceWSHandler


def _make_event(eid: str = "evt_test1", category: str = "sms", body: str = "hello") -> NotificationEvent:
    return NotificationEvent(
        type="notification",
        priority=Priority.NORMAL,
        category=category,
        payload={"body": body, "source_id": "src1"},
        id=eid,
        timestamp=time.time(),
    )


def _make_stack():
    store = QueueStore(":memory:")
    dispatcher = NotificationDispatcher(store)
    handler = DeviceWSHandler(dispatcher)
    return store, dispatcher, handler


# ── Test 1: register and unregister ──────────────────────────────────

def test_register_and_unregister():
    _store, _dispatcher, handler = _make_stack()
    ws = MagicMock()

    handler.register(ws, "device-001")
    assert "device-001" in handler._devices

    handler.unregister("device-001")
    assert "device-001" not in handler._devices


# ── Test 2: broadcast sends to all ───────────────────────────────────

def test_broadcast_sends_to_all():
    _store, _dispatcher, handler = _make_stack()
    ws1 = MagicMock()
    ws2 = MagicMock()

    handler.register(ws1, "dev-a")
    handler.register(ws2, "dev-b")

    event_dict = {"type": "notification", "id": "evt_1", "payload": {}}
    handler.broadcast(event_dict)

    ws1.send_json.assert_called_once_with(event_dict)
    ws2.send_json.assert_called_once_with(event_dict)


# ── Test 3: handle_ack marks delivered ────────────────────────────────

def test_handle_ack_marks_delivered():
    store, dispatcher, handler = _make_stack()
    event = _make_event("evt_ack1")
    store.push(event)

    # Verify it's pending
    assert len(store.get_pending()) == 1

    handler.handle_message({"type": "ack", "event_id": "evt_ack1"})

    # Now it should be delivered (no longer pending)
    assert len(store.get_pending()) == 0


# ── Test 4: handle_reconnect replays missed ───────────────────────────

def test_handle_reconnect_replays_missed():
    store, dispatcher, handler = _make_stack()

    t_before = time.time() - 10
    evt1 = _make_event("evt_r1")
    evt1.timestamp = time.time() - 5
    evt2 = _make_event("evt_r2")
    evt2.timestamp = time.time() - 2

    store.push(evt1)
    store.push(evt2)

    ws = MagicMock()
    handler.handle_reconnect(ws, last_ts=t_before)

    assert ws.send_json.call_count == 2
    # Verify the replayed event IDs
    sent_ids = [call.args[0]["id"] for call in ws.send_json.call_args_list]
    assert "evt_r1" in sent_ids
    assert "evt_r2" in sent_ids
