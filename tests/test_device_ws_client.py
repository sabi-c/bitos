"""Tests for DeviceWSClient — no real WebSocket connections."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from notifications.ws_client import DeviceWSClient, MAX_BACKOFF_S


def _make_client() -> DeviceWSClient:
    return DeviceWSClient(url="ws://localhost:9999/ws/device", device_id="test_device")


# ── 1. Initial state ─────────────────────────────────────────────────


def test_initial_state_disconnected():
    client = _make_client()
    assert client.connected is False
    assert client.last_event_id is None


# ── 2. on_event callback fires ──────────────────────────────────────


def test_on_event_fires_from_handle_message():
    client = _make_client()
    received = []
    client.on_event = lambda data: received.append(data)

    raw = json.dumps({"type": "notification", "id": "evt_1", "body": "hello"})
    client._handle_message(raw)

    assert len(received) == 1
    assert received[0]["type"] == "notification"
    assert received[0]["id"] == "evt_1"


# ── 3. Backoff ───────────────────────────────────────────────────────


def test_reconnect_backoff_exponential_capped():
    client = _make_client()
    backoffs = [client._next_backoff() for _ in range(8)]
    assert backoffs[0] == 1.0   # 2^0
    assert backoffs[1] == 2.0   # 2^1
    assert backoffs[2] == 4.0   # 2^2
    assert backoffs[3] == 8.0   # 2^3
    assert backoffs[4] == 16.0  # 2^4
    assert backoffs[5] == MAX_BACKOFF_S  # 2^5 = 32 > 30 -> capped
    assert backoffs[6] == MAX_BACKOFF_S
    assert backoffs[7] == MAX_BACKOFF_S


# ── 4. Tracks last_event_id ─────────────────────────────────────────


def test_tracks_last_event_id():
    client = _make_client()
    client.on_event = lambda data: None

    client._handle_message(json.dumps({"id": "evt_1"}))
    assert client.last_event_id == "evt_1"

    client._handle_message(json.dumps({"id": "evt_2"}))
    assert client.last_event_id == "evt_2"

    # Message without id does not change last_event_id
    client._handle_message(json.dumps({"type": "ping"}))
    assert client.last_event_id == "evt_2"


# ── 5. Malformed messages ignored ───────────────────────────────────


def test_ignores_malformed_messages():
    client = _make_client()
    received = []
    client.on_event = lambda data: received.append(data)

    # Invalid JSON
    client._handle_message("not json at all {{{")
    assert len(received) == 0

    # Valid JSON but not a dict
    client._handle_message(json.dumps([1, 2, 3]))
    assert len(received) == 0

    # Valid dict still works
    client._handle_message(json.dumps({"type": "ok"}))
    assert len(received) == 1
