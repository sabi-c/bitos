# Notification System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace poll-based notifications with a real-time WebSocket event bus, add tiered delivery (banner/toast/badge), animated rendering with progress bars, DND-aware routing, and in-chat tool result banners.

**Architecture:** Server-side NotificationDispatcher collects events from integrations and agent heartbeat, deduplicates, assigns priority tiers, persists to SQLite queue, and pushes to connected devices via `/ws/device`. Device-side NotificationRouter receives events, checks DND state (recording/speaking), and routes to appropriate delivery style. Existing NotificationBanner, NotificationToast, and NotificationQueue are upgraded with animations and progress bars.

**Tech Stack:** Python, pygame, FastAPI, websockets, SQLite

**Design doc:** `docs/plans/2026-03-16-notification-system-design.md`

---

### Task 1: Server-Side Notification Dispatcher

**Files:**
- Create: `server/notifications/__init__.py`
- Create: `server/notifications/dispatcher.py`
- Create: `server/notifications/models.py`
- Create: `server/notifications/queue_store.py`
- Test: `tests/test_notification_dispatcher.py`

**Step 1: Write the failing test**

```python
# tests/test_notification_dispatcher.py
import unittest
from server.notifications.models import NotificationEvent, Priority
from server.notifications.dispatcher import NotificationDispatcher
from server.notifications.queue_store import NotificationQueueStore


class TestNotificationDispatcher(unittest.TestCase):
    def setUp(self):
        self.store = NotificationQueueStore(":memory:")
        self.dispatcher = NotificationDispatcher(self.store)
        self.delivered = []
        self.dispatcher.register_callback(lambda evt: self.delivered.append(evt))

    def test_dispatch_stores_and_delivers(self):
        evt = NotificationEvent(
            type="notification",
            priority=Priority.HIGH,
            category="sms",
            payload={"title": "Alex", "body": "Hey there", "app": "iMessage"},
        )
        self.dispatcher.dispatch(evt)
        self.assertEqual(len(self.delivered), 1)
        self.assertEqual(self.delivered[0].category, "sms")
        # Also persisted
        pending = self.store.get_pending()
        self.assertEqual(len(pending), 1)

    def test_dedup_within_window(self):
        evt = NotificationEvent(
            type="notification",
            priority=Priority.HIGH,
            category="sms",
            payload={"title": "Alex", "body": "Hey there", "app": "iMessage",
                     "source_id": "chat_123"},
        )
        self.dispatcher.dispatch(evt)
        self.dispatcher.dispatch(evt)  # duplicate
        self.assertEqual(len(self.delivered), 1)

    def test_dedup_different_body_not_deduped(self):
        evt1 = NotificationEvent(
            type="notification", priority=Priority.HIGH, category="sms",
            payload={"title": "Alex", "body": "Hey", "source_id": "chat_123"},
        )
        evt2 = NotificationEvent(
            type="notification", priority=Priority.HIGH, category="sms",
            payload={"title": "Alex", "body": "Different", "source_id": "chat_123"},
        )
        self.dispatcher.dispatch(evt1)
        self.dispatcher.dispatch(evt2)
        self.assertEqual(len(self.delivered), 2)

    def test_ack_marks_delivered(self):
        evt = NotificationEvent(
            type="notification", priority=Priority.NORMAL, category="mail",
            payload={"title": "Newsletter", "body": "Weekly digest"},
        )
        self.dispatcher.dispatch(evt)
        self.store.mark_delivered(evt.id)
        pending = self.store.get_pending()
        self.assertEqual(len(pending), 0)

    def test_get_since_replays_missed(self):
        evts = []
        for i in range(3):
            evt = NotificationEvent(
                type="notification", priority=Priority.NORMAL, category="mail",
                payload={"title": f"Mail {i}", "body": f"Body {i}"},
            )
            self.dispatcher.dispatch(evt)
            evts.append(evt)
        missed = self.store.get_since(evts[0].id)
        self.assertEqual(len(missed), 2)  # events after first


class TestNotificationQueueStore(unittest.TestCase):
    def setUp(self):
        self.store = NotificationQueueStore(":memory:")

    def test_persist_and_retrieve(self):
        evt = NotificationEvent(
            type="reminder", priority=Priority.CRITICAL, category="reminder",
            payload={"title": "Dinner", "body": "Time for dinner"},
        )
        self.store.push(evt)
        pending = self.store.get_pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], evt.id)

    def test_expire_old_events(self):
        self.store.push(NotificationEvent(
            type="notification", priority=Priority.LOW, category="system",
            payload={"body": "old"},
        ))
        self.store.expire_older_than_hours(0)  # expire everything
        self.assertEqual(len(self.store.get_pending()), 0)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_notification_dispatcher.py -v`
Expected: FAIL with ModuleNotFoundError (server.notifications doesn't exist)

**Step 3: Write minimal implementation**

```python
# server/notifications/__init__.py
"""Server-side notification dispatch system."""

# server/notifications/models.py
from __future__ import annotations
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum


class Priority(IntEnum):
    CRITICAL = 1  # P1: full banner, wake, chime
    HIGH = 2      # P2: banner, wake if sleeping
    NORMAL = 3    # P3: toast strip
    LOW = 4       # P4: badge only
    SILENT = 5    # P5: queue only


CATEGORY_DEFAULTS = {
    "sms": Priority.HIGH,
    "mail": Priority.NORMAL,
    "calendar": Priority.HIGH,
    "task": Priority.HIGH,
    "agent": Priority.HIGH,
    "reminder": Priority.CRITICAL,
    "tool": Priority.NORMAL,
    "system": Priority.LOW,
}

CATEGORY_COLORS = {
    "sms": (60, 130, 220),
    "mail": (180, 140, 60),
    "calendar": (80, 180, 120),
    "task": (160, 100, 220),
    "agent": (100, 200, 200),
    "reminder": (220, 80, 80),
    "tool": (100, 200, 200),
    "system": (120, 120, 120),
}


@dataclass
class NotificationEvent:
    type: str  # notification, reminder, agent_message, tool_result, activity_sync
    priority: Priority
    category: str
    payload: dict
    id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    timestamp: float = field(default_factory=time.time)

    @property
    def dedup_key(self) -> str:
        source_id = self.payload.get("source_id", "")
        body = self.payload.get("body", "")
        body_hash = hashlib.md5(body.encode()).hexdigest()[:8]
        return f"{self.category}:{source_id}:{body_hash}"

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "id": self.id,
            "priority": int(self.priority),
            "category": self.category,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


# server/notifications/queue_store.py
from __future__ import annotations
import json
import sqlite3
import time
from .models import NotificationEvent


class NotificationQueueStore:
    """Persistent event queue backed by SQLite."""

    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_queue (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                priority INTEGER NOT NULL,
                category TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL,
                delivered_at REAL
            )
        """)
        self._conn.commit()

    def push(self, event: NotificationEvent) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO notification_queue "
            "(id, type, priority, category, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event.id, event.type, int(event.priority), event.category,
             json.dumps(event.payload), event.timestamp),
        )
        self._conn.commit()

    def get_pending(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM notification_queue WHERE delivered_at IS NULL "
            "ORDER BY priority ASC, created_at ASC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_delivered(self, event_id: str) -> None:
        self._conn.execute(
            "UPDATE notification_queue SET delivered_at = ? WHERE id = ?",
            (time.time(), event_id),
        )
        self._conn.commit()

    def get_since(self, last_event_id: str, limit: int = 50) -> list[dict]:
        row = self._conn.execute(
            "SELECT created_at FROM notification_queue WHERE id = ?",
            (last_event_id,),
        ).fetchone()
        if not row:
            return self.get_pending(limit)
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM notification_queue WHERE created_at > ? "
            "AND delivered_at IS NULL ORDER BY priority ASC, created_at ASC LIMIT ?",
            (row["created_at"], limit),
        ).fetchall()]

    def expire_older_than_hours(self, hours: int) -> int:
        cutoff = time.time() - hours * 3600
        cur = self._conn.execute(
            "DELETE FROM notification_queue WHERE created_at < ?", (cutoff,)
        )
        self._conn.commit()
        return cur.rowcount


# server/notifications/dispatcher.py
from __future__ import annotations
import time
from typing import Callable
from .models import NotificationEvent
from .queue_store import NotificationQueueStore

DEDUP_WINDOW_S = 60


class NotificationDispatcher:
    """Central notification hub: dedup, persist, push to devices."""

    def __init__(self, store: NotificationQueueStore):
        self._store = store
        self._callbacks: list[Callable[[NotificationEvent], None]] = []
        self._recent_dedup: dict[str, float] = {}  # dedup_key -> timestamp

    def register_callback(self, cb: Callable[[NotificationEvent], None]) -> None:
        self._callbacks.append(cb)

    def unregister_callback(self, cb: Callable[[NotificationEvent], None]) -> None:
        self._callbacks = [c for c in self._callbacks if c is not cb]

    def dispatch(self, event: NotificationEvent) -> bool:
        """Dispatch event. Returns False if deduped."""
        # Dedup check
        now = time.time()
        key = event.dedup_key
        if key in self._recent_dedup:
            if now - self._recent_dedup[key] < DEDUP_WINDOW_S:
                return False
        self._recent_dedup[key] = now

        # Clean old dedup entries
        self._recent_dedup = {
            k: t for k, t in self._recent_dedup.items()
            if now - t < DEDUP_WINDOW_S * 2
        }

        # Persist
        self._store.push(event)

        # Push to connected devices
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception:
                pass

        return True
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_notification_dispatcher.py -v`
Expected: PASS (all 7 tests)

**Step 5: Commit**

```bash
git add server/notifications/ tests/test_notification_dispatcher.py
git commit -m "feat: server-side notification dispatcher with dedup and persistent queue"
```

---

### Task 2: WebSocket Device Endpoint

**Files:**
- Create: `server/notifications/ws_handler.py`
- Modify: `server/main.py` (add /ws/device endpoint)
- Test: `tests/test_ws_device.py`

**Step 1: Write the failing test**

```python
# tests/test_ws_device.py
import unittest
import json
from unittest.mock import MagicMock, AsyncMock
from server.notifications.ws_handler import DeviceWSHandler


class TestDeviceWSHandler(unittest.TestCase):
    def test_register_and_unregister(self):
        dispatcher = MagicMock()
        handler = DeviceWSHandler(dispatcher)
        ws = MagicMock()
        ws.id = "dev_001"
        handler.register(ws, "dev_001")
        self.assertIn("dev_001", handler.devices)
        handler.unregister("dev_001")
        self.assertNotIn("dev_001", handler.devices)

    def test_broadcast_sends_to_all(self):
        dispatcher = MagicMock()
        handler = DeviceWSHandler(dispatcher)
        ws1 = MagicMock()
        ws2 = MagicMock()
        handler.register(ws1, "dev_001")
        handler.register(ws2, "dev_002")
        event_dict = {"type": "notification", "id": "evt_123", "payload": {}}
        handler.broadcast(event_dict)
        self.assertEqual(ws1.send_json.call_count, 1)
        self.assertEqual(ws2.send_json.call_count, 1)

    def test_handle_ack(self):
        store = MagicMock()
        dispatcher = MagicMock()
        dispatcher._store = store
        handler = DeviceWSHandler(dispatcher)
        handler.handle_message({"type": "ack", "id": "evt_123"})
        store.mark_delivered.assert_called_once_with("evt_123")

    def test_handle_reconnect_replays(self):
        store = MagicMock()
        store.get_since.return_value = [
            {"id": "evt_2", "type": "notification", "priority": 3,
             "category": "mail", "payload": "{}", "created_at": 1.0},
        ]
        dispatcher = MagicMock()
        dispatcher._store = store
        handler = DeviceWSHandler(dispatcher)
        ws = MagicMock()
        handler.register(ws, "dev_001")
        handler.handle_reconnect(ws, "evt_1")
        store.get_since.assert_called_once_with("evt_1")
        ws.send_json.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ws_device.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# server/notifications/ws_handler.py
from __future__ import annotations
import json
import logging
from typing import Any
from .dispatcher import NotificationDispatcher
from .models import NotificationEvent

log = logging.getLogger(__name__)


class DeviceWSHandler:
    """Manages WebSocket connections from BITOS devices."""

    def __init__(self, dispatcher: NotificationDispatcher):
        self._dispatcher = dispatcher
        self.devices: dict[str, Any] = {}  # device_id -> ws

        # Register as dispatch callback
        dispatcher.register_callback(self._on_event)

    def register(self, ws, device_id: str) -> None:
        self.devices[device_id] = ws
        log.info("Device %s connected", device_id)

    def unregister(self, device_id: str) -> None:
        self.devices.pop(device_id, None)
        log.info("Device %s disconnected", device_id)

    def _on_event(self, event: NotificationEvent) -> None:
        self.broadcast(event.to_dict())

    def broadcast(self, event_dict: dict) -> None:
        dead = []
        for dev_id, ws in self.devices.items():
            try:
                ws.send_json(event_dict)
            except Exception:
                dead.append(dev_id)
        for dev_id in dead:
            self.unregister(dev_id)

    def handle_message(self, data: dict) -> None:
        msg_type = data.get("type")
        if msg_type == "ack":
            self._dispatcher._store.mark_delivered(data.get("id", ""))
        elif msg_type == "dnd":
            log.info("Device DND: %s reason=%s", data.get("active"), data.get("reason"))

    def handle_reconnect(self, ws, last_event_id: str) -> None:
        missed = self._dispatcher._store.get_since(last_event_id)
        for row in missed:
            payload = row.get("payload", "{}")
            if isinstance(payload, str):
                payload = json.loads(payload)
            ws.send_json({
                "type": row["type"],
                "id": row["id"],
                "priority": row["priority"],
                "category": row["category"],
                "payload": payload,
            })
```

Then add to `server/main.py` the WebSocket endpoint (after existing WS endpoints):

```python
# In server/main.py — add near other WebSocket endpoints
from server.notifications.dispatcher import NotificationDispatcher
from server.notifications.queue_store import NotificationQueueStore
from server.notifications.ws_handler import DeviceWSHandler

# Initialize (near app startup)
_notif_store = NotificationQueueStore("data/notifications.db")
_notif_dispatcher = NotificationDispatcher(_notif_store)
_device_ws = DeviceWSHandler(_notif_dispatcher)

@app.websocket("/ws/device")
async def ws_device(websocket: WebSocket):
    await websocket.accept()
    device_id = websocket.query_params.get("device_id", "unknown")
    _device_ws.register(websocket, device_id)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type == "reconnect":
                _device_ws.handle_reconnect(websocket, data.get("last_event_id", ""))
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                _device_ws.handle_message(data)
    except Exception:
        pass
    finally:
        _device_ws.unregister(device_id)
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_ws_device.py -v`
Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add server/notifications/ws_handler.py server/main.py tests/test_ws_device.py
git commit -m "feat: WebSocket /ws/device endpoint for real-time notification push"
```

---

### Task 3: Device-Side Notification Router

**Files:**
- Create: `device/notifications/router.py`
- Test: `tests/test_notification_router.py`

**Step 1: Write the failing test**

```python
# tests/test_notification_router.py
import os
import sys
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestNotificationRouter(unittest.TestCase):
    def setUp(self):
        from device.notifications.router import NotificationRouter
        self.show_banner = MagicMock()
        self.show_toast = MagicMock()
        self.set_badge = MagicMock()
        self.router = NotificationRouter(
            on_banner=self.show_banner,
            on_toast=self.show_toast,
            on_badge=self.set_badge,
        )

    def test_p1_shows_banner(self):
        self.router.on_event({
            "type": "reminder", "id": "evt_1", "priority": 1,
            "category": "reminder",
            "payload": {"title": "Dinner", "body": "Time for dinner"},
        })
        self.show_banner.assert_called_once()

    def test_p2_shows_banner(self):
        self.router.on_event({
            "type": "notification", "id": "evt_2", "priority": 2,
            "category": "sms",
            "payload": {"title": "Alex", "body": "Hey"},
        })
        self.show_banner.assert_called_once()

    def test_p3_shows_toast(self):
        self.router.on_event({
            "type": "notification", "id": "evt_3", "priority": 3,
            "category": "mail",
            "payload": {"title": "Newsletter", "body": "Weekly"},
        })
        self.show_toast.assert_called_once()

    def test_p4_shows_badge_only(self):
        self.router.on_event({
            "type": "notification", "id": "evt_4", "priority": 4,
            "category": "system",
            "payload": {"body": "Update available"},
        })
        self.show_banner.assert_not_called()
        self.show_toast.assert_not_called()
        self.set_badge.assert_called()

    def test_dnd_queues_notification(self):
        self.router.set_dnd(True, "recording")
        self.router.on_event({
            "type": "notification", "id": "evt_5", "priority": 2,
            "category": "sms",
            "payload": {"title": "Alex", "body": "Hey"},
        })
        self.show_banner.assert_not_called()
        self.assertEqual(len(self.router._queue), 1)

    def test_dnd_clear_drains_queue(self):
        self.router.set_dnd(True, "recording")
        self.router.on_event({
            "type": "notification", "id": "evt_6", "priority": 2,
            "category": "sms", "payload": {"title": "Alex", "body": "Hey"},
        })
        self.router.set_dnd(False)
        # drain_queue called internally
        self.show_banner.assert_called_once()

    def test_p1_breaks_through_dnd(self):
        """P1 (critical reminders) always deliver even during DND."""
        self.router.set_dnd(True, "speaking")
        self.router.on_event({
            "type": "reminder", "id": "evt_7", "priority": 1,
            "category": "reminder",
            "payload": {"title": "URGENT", "body": "Now"},
        })
        self.show_banner.assert_called_once()

    def test_coalesce_when_queue_large(self):
        self.router.set_dnd(True, "recording")
        for i in range(6):
            self.router.on_event({
                "type": "notification", "id": f"evt_{i}", "priority": 3,
                "category": "mail",
                "payload": {"title": f"Mail {i}", "body": f"Body {i}"},
            })
        self.router.set_dnd(False)
        # Should coalesce into summary toast instead of 6 individual ones
        self.show_toast.assert_called_once()
        call_args = self.show_toast.call_args
        self.assertIn("6", call_args[0][0]["body"])


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_notification_router.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# device/notifications/router.py
"""NotificationRouter — DND-aware event routing by priority tier."""
from __future__ import annotations

from typing import Callable


class NotificationRouter:
    """Routes incoming WS events to banner/toast/badge based on priority and DND state."""

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

    def set_dnd(self, active: bool, reason: str = "") -> None:
        self._dnd_active = active
        self._dnd_reason = reason if active else ""
        if not active:
            self._drain_queue()

    def on_event(self, event: dict) -> None:
        priority = event.get("priority", 3)

        # Always update badge count
        if priority <= 4:
            self._unread_count += 1
            if self._on_badge:
                self._on_badge(self._unread_count)

        # P1 breaks through DND
        if self._dnd_active and priority > 1:
            self._queue.append(event)
            return

        self._deliver(event)

    def _deliver(self, event: dict) -> None:
        priority = event.get("priority", 3)
        if priority <= 2:
            self._on_banner(event)
        elif priority == 3:
            self._on_toast(event)
        # P4-P5: badge only (already handled in on_event)

    def _drain_queue(self) -> None:
        if not self._queue:
            return

        if len(self._queue) > self.COALESCE_THRESHOLD:
            count = len(self._queue)
            summary = {
                "type": "notification",
                "id": "evt_summary",
                "priority": 3,
                "category": "system",
                "payload": {
                    "title": "Notifications",
                    "body": f"{count} notifications while you were busy",
                    "app": "BITOS",
                },
            }
            self._queue.clear()
            self._on_toast(summary)
            return

        # Sort by priority then timestamp
        self._queue.sort(key=lambda e: (e.get("priority", 3), e.get("timestamp", 0)))
        for event in self._queue:
            self._deliver(event)
        self._queue.clear()

    def clear_unread(self) -> None:
        self._unread_count = 0
        if self._on_badge:
            self._on_badge(0)
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_notification_router.py -v`
Expected: PASS (all 8 tests)

**Step 5: Commit**

```bash
git add device/notifications/router.py tests/test_notification_router.py
git commit -m "feat: device-side notification router with DND and priority tiers"
```

---

### Task 4: Animated Banner Rendering

**Files:**
- Modify: `device/overlays/notification_banner.py`
- Test: `tests/test_animated_banner.py`

**Step 1: Write the failing test**

```python
# tests/test_animated_banner.py
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

from device.overlays.notification_banner import NotificationBanner


class TestAnimatedBanner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_banner(self, **kwargs):
        defaults = dict(
            app="iMessage", icon="S", message="Hey there",
            time_str="14:30", category="sms",
        )
        defaults.update(kwargs)
        return NotificationBanner(**defaults)

    def test_has_progress_property(self):
        b = self._make_banner()
        self.assertAlmostEqual(b.progress, 1.0, places=1)

    def test_progress_decreases_with_time(self):
        b = self._make_banner(duration_ms=5000)
        b.tick(2500)
        self.assertAlmostEqual(b.progress, 0.5, places=1)

    def test_has_category_color(self):
        b = self._make_banner(category="sms")
        self.assertEqual(b.category_color, (60, 130, 220))

    def test_slide_offset_starts_offscreen(self):
        b = self._make_banner()
        self.assertLess(b.slide_y_offset, 0)

    def test_slide_settles_after_entrance(self):
        b = self._make_banner()
        b.tick(250)  # past 200ms entrance
        self.assertEqual(b.slide_y_offset, 0)

    def test_exit_animation_starts_near_end(self):
        b = self._make_banner(duration_ms=5000)
        b.tick(4900)  # near end
        self.assertLessEqual(b.slide_y_offset, 0)

    def test_render_smoke(self):
        b = self._make_banner()
        b.tick(100)
        surf = pygame.Surface((240, 280))
        b.render(surf)  # should not crash


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_animated_banner.py -v`
Expected: FAIL (NotificationBanner doesn't have progress/category/slide properties)

**Step 3: Update NotificationBanner implementation**

Modify `device/overlays/notification_banner.py` to add:

- `category: str = "system"` field
- `progress` property: `max(0, 1.0 - self.elapsed_ms / self.duration_ms)`
- `category_color` property: lookup from CATEGORY_COLORS dict
- `slide_y_offset` property: entrance (0-200ms) slide-down with ease-out + 2px bounce, exit (last 150ms) slide-up
- Updated `render()`: draw progress bar (2px, colored, shrinking), use slide offset for y position
- Updated `_render_compact_strip()` and `_render_full_banner()`: add progress bar at bottom

Key constants to add:
```python
ENTRANCE_MS = 200
EXIT_MS = 150
BANNER_H = 72
PROGRESS_BAR_H = 2
CATEGORY_COLORS = {
    "sms": (60, 130, 220),
    "mail": (180, 140, 60),
    "calendar": (80, 180, 120),
    "task": (160, 100, 220),
    "agent": (100, 200, 200),
    "reminder": (220, 80, 80),
    "tool": (100, 200, 200),
    "system": (120, 120, 120),
}
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_animated_banner.py -v`
Expected: PASS (all 7 tests)

**Step 5: Commit**

```bash
git add device/overlays/notification_banner.py tests/test_animated_banner.py
git commit -m "feat: animated notification banner with progress bar and slide transitions"
```

---

### Task 5: Animated Toast Rendering

**Files:**
- Modify: `device/overlays/notification.py` (NotificationToast class)
- Test: `tests/test_animated_toast.py`

**Step 1: Write the failing test**

```python
# tests/test_animated_toast.py
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

from device.overlays.notification import NotificationToast


class TestAnimatedToast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_toast(self, **kwargs):
        defaults = dict(
            app="Gmail", icon="M", message="Weekly digest",
            time_str="14:30", category="mail",
        )
        defaults.update(kwargs)
        return NotificationToast(**defaults)

    def test_has_progress(self):
        t = self._make_toast(duration_ms=3000)
        t.tick(1500)
        self.assertAlmostEqual(t.progress, 0.5, places=1)

    def test_has_category_color(self):
        t = self._make_toast(category="mail")
        self.assertEqual(t.category_color, (180, 140, 60))

    def test_slide_entrance(self):
        t = self._make_toast()
        self.assertLess(t.slide_y_offset, 0)
        t.tick(200)
        self.assertEqual(t.slide_y_offset, 0)

    def test_render_smoke(self):
        t = self._make_toast()
        t.tick(100)
        surf = pygame.Surface((240, 280))
        t.render(surf, {})  # should not crash


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_animated_toast.py -v`
Expected: FAIL

**Step 3: Update NotificationToast**

Add to `NotificationToast`:
- `category: str = "system"` field
- `progress` property
- `category_color` property
- `slide_y_offset` property (same entrance/exit pattern as banner, smaller scale)
- Mini progress bar (2px) at bottom of 28px strip
- 3s default duration (change from 5s)

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_animated_toast.py -v`
Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add device/overlays/notification.py tests/test_animated_toast.py
git commit -m "feat: animated toast with progress bar and slide entrance"
```

---

### Task 6: Device WebSocket Client

**Files:**
- Create: `device/notifications/ws_client.py`
- Modify: `device/notifications/poller.py` (delegate to WS when connected)
- Test: `tests/test_device_ws_client.py`

**Step 1: Write the failing test**

```python
# tests/test_device_ws_client.py
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from device.notifications.ws_client import DeviceWSClient


class TestDeviceWSClient(unittest.TestCase):
    def test_initial_state_disconnected(self):
        client = DeviceWSClient("ws://localhost:8000/ws/device")
        self.assertFalse(client.connected)

    def test_on_event_callback_fires(self):
        client = DeviceWSClient("ws://localhost:8000/ws/device")
        events = []
        client.on_event = lambda e: events.append(e)
        client._handle_message('{"type": "notification", "id": "evt_1", "priority": 2, "category": "sms", "payload": {"body": "hi"}}')
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["category"], "sms")

    def test_reconnect_backoff(self):
        client = DeviceWSClient("ws://localhost:8000/ws/device")
        self.assertEqual(client._next_backoff(), 1)
        client._reconnect_attempts = 1
        self.assertEqual(client._next_backoff(), 2)
        client._reconnect_attempts = 5
        self.assertEqual(client._next_backoff(), 30)  # capped at 30

    def test_tracks_last_event_id(self):
        client = DeviceWSClient("ws://localhost:8000/ws/device")
        client._handle_message('{"type": "notification", "id": "evt_42", "priority": 3, "category": "mail", "payload": {}}')
        self.assertEqual(client._last_event_id, "evt_42")

    def test_ignores_malformed_messages(self):
        client = DeviceWSClient("ws://localhost:8000/ws/device")
        client._handle_message("not json")  # should not crash
        client._handle_message("{}")  # missing fields, should not crash


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_device_ws_client.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# device/notifications/ws_client.py
"""WebSocket client for real-time notification delivery from server."""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)

MAX_BACKOFF_S = 30


class DeviceWSClient:
    """Persistent WebSocket connection to server /ws/device endpoint."""

    def __init__(self, url: str, device_id: str = "bitos_main"):
        self._url = url
        self._device_id = device_id
        self._ws = None
        self._connected = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._reconnect_attempts = 0
        self._last_event_id: str | None = None

        # Callbacks
        self.on_event: Callable[[dict], None] | None = None
        self.on_connect: Callable[[], None] | None = None
        self.on_disconnect: Callable[[], None] | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2)

    def send_ack(self, event_id: str) -> None:
        self._send({"type": "ack", "id": event_id})

    def send_dnd(self, active: bool, reason: str = "") -> None:
        self._send({"type": "dnd", "active": active, "reason": reason})

    def _send(self, data: dict) -> None:
        if self._ws and self._connected:
            try:
                self._ws.send(json.dumps(data))
            except Exception:
                pass

    def _run_loop(self) -> None:
        try:
            import websocket
        except ImportError:
            log.warning("websocket-client not installed, WS notifications disabled")
            return

        while not self._stop.is_set():
            try:
                url = f"{self._url}?device_id={self._device_id}"
                self._ws = websocket.WebSocket()
                self._ws.connect(url, timeout=5)
                self._connected = True
                self._reconnect_attempts = 0

                if self.on_connect:
                    self.on_connect()

                # Request replay of missed events
                if self._last_event_id:
                    self._send({"type": "reconnect",
                                "last_event_id": self._last_event_id})

                # Receive loop
                while not self._stop.is_set():
                    self._ws.settimeout(35)  # slightly longer than server ping
                    try:
                        raw = self._ws.recv()
                        if raw:
                            self._handle_message(raw)
                    except websocket.WebSocketTimeoutException:
                        self._send({"type": "ping"})

            except Exception as e:
                log.debug("WS connection error: %s", e)
            finally:
                self._connected = False
                if self.on_disconnect:
                    try:
                        self.on_disconnect()
                    except Exception:
                        pass

            if not self._stop.is_set():
                backoff = self._next_backoff()
                self._reconnect_attempts += 1
                self._stop.wait(backoff)

    def _handle_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return

        msg_type = data.get("type")
        if not msg_type:
            return

        if msg_type == "pong":
            return

        # Track last event ID for reconnection replay
        event_id = data.get("id")
        if event_id:
            self._last_event_id = event_id

        if self.on_event:
            try:
                self.on_event(data)
            except Exception:
                log.exception("Error in on_event callback")

    def _next_backoff(self) -> int:
        return min(2 ** self._reconnect_attempts, MAX_BACKOFF_S)
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_device_ws_client.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add device/notifications/ws_client.py tests/test_device_ws_client.py
git commit -m "feat: device WebSocket client with auto-reconnect and event replay"
```

---

### Task 7: Wire Router + WS Client into Device Main

**Files:**
- Modify: `device/main.py`
- Modify: `device/screens/manager.py` (add DND state reporting)

**Step 1: Identify integration points**

Read `device/main.py` lines 297-340 (current poller wiring) and `device/screens/manager.py` lines 167-181 (input routing).

**Step 2: Wire NotificationRouter and DeviceWSClient**

In `device/main.py`, after the existing poller setup:

```python
from device.notifications.router import NotificationRouter
from device.notifications.ws_client import DeviceWSClient

# Create router with delivery callbacks
def _show_banner_from_event(event: dict):
    payload = event.get("payload", {})
    was_sleeping = idle_mgr.state in ("dim", "sleep")
    idle_mgr.wake()
    banner = NotificationBanner(
        app=payload.get("app", event.get("category", "").upper()),
        icon=payload.get("icon", "!"),
        message=payload.get("body", ""),
        time_str=payload.get("time_str", time.strftime("%H:%M")),
        was_sleeping=was_sleeping,
        category=event.get("category", "system"),
        on_reply=on_banner_reply,
        on_dismiss=on_banner_dismiss,
    )
    screen_mgr.show_banner(banner)

def _show_toast_from_event(event: dict):
    payload = event.get("payload", {})
    notification_queue.push(NotificationToast(
        app=payload.get("app", event.get("category", "").upper()),
        icon=payload.get("icon", "!"),
        message=payload.get("body", ""),
        time_str=time.strftime("%H:%M"),
        category=event.get("category", "system"),
    ))

notification_router = NotificationRouter(
    on_banner=_show_banner_from_event,
    on_toast=_show_toast_from_event,
    on_badge=lambda count: status_bar.set_unread_count(count),
)

# WebSocket client
server_url = os.environ.get("BITOS_SERVER_URL", "ws://localhost:8000")
ws_client = DeviceWSClient(f"{server_url}/ws/device")
ws_client.on_event = notification_router.on_event
ws_client.start()
```

Also wire DND state changes:
- In chat panel RECORDING state entry: `notification_router.set_dnd(True, "recording")`
- In chat panel RECORDING state exit: `notification_router.set_dnd(False)`
- In chat panel SPEAKING state entry: `notification_router.set_dnd(True, "speaking")`
- In chat panel SPEAKING→IDLE transition: `notification_router.set_dnd(False)`

**Step 3: Test manually**

Run: `python3 -m pytest tests/ -v --ignore=tests/test_chat_panel.py --ignore=tests/test_mail_panel.py`
Expected: All existing tests still pass

**Step 4: Commit**

```bash
git add device/main.py
git commit -m "feat: wire notification router + WS client into device main loop"
```

---

### Task 8: In-Chat Tool Result Banners

**Files:**
- Create: `device/ui/components/tool_banner.py`
- Test: `tests/test_tool_banner.py`

**Step 1: Write the failing test**

```python
# tests/test_tool_banner.py
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

from device.ui.components.tool_banner import ToolBanner


class TestToolBanner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_task_banner(self):
        b = ToolBanner(tool="create_task", summary="Buy groceries",
                       detail="Due: Tomorrow 5pm")
        self.assertEqual(b.accent_color, (160, 100, 220))  # purple for task

    def test_reminder_banner(self):
        b = ToolBanner(tool="schedule_reminder", summary="Dinner at 5pm")
        self.assertEqual(b.accent_color, (220, 80, 80))  # red for reminder

    def test_calendar_banner(self):
        b = ToolBanner(tool="create_event", summary="Team standup",
                       detail="Tomorrow 9:00 AM")
        self.assertEqual(b.accent_color, (80, 180, 120))  # green for calendar

    def test_render_smoke(self):
        b = ToolBanner(tool="create_task", summary="Buy groceries",
                       detail="Due: Tomorrow")
        surf = pygame.Surface((156, 50))
        h = b.render(surf, y=0)
        self.assertGreater(h, 0)

    def test_render_no_detail(self):
        b = ToolBanner(tool="create_task", summary="Buy groceries")
        surf = pygame.Surface((156, 50))
        h = b.render(surf, y=0)
        self.assertGreater(h, 0)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_tool_banner.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# device/ui/components/tool_banner.py
"""Inline tool result banner for chat messages."""
from __future__ import annotations

import pygame

from device.display.theme import get_font
from device.display.tokens import DIM3, WHITE

ACCENT_W = 4
PAD_X = 6
PAD_Y = 3
FONT_SIZE = 10

TOOL_COLORS = {
    "create_task": (160, 100, 220),    # purple
    "update_task": (160, 100, 220),
    "complete_task": (160, 100, 220),
    "schedule_reminder": (220, 80, 80), # red
    "create_event": (80, 180, 120),     # green
    "update_event": (80, 180, 120),
    "homekit": (220, 160, 60),          # orange
    "send_message": (60, 130, 220),     # blue
}

DEFAULT_COLOR = (100, 200, 200)  # cyan


class ToolBanner:
    """Compact inline banner showing agent tool result."""

    def __init__(self, tool: str, summary: str, detail: str = ""):
        self.tool = tool
        self.summary = summary
        self.detail = detail

    @property
    def accent_color(self) -> tuple[int, int, int]:
        for key, color in TOOL_COLORS.items():
            if key in self.tool:
                return color
        return DEFAULT_COLOR

    def render(self, surface: pygame.Surface, y: int) -> int:
        """Render banner at y position. Returns total height used."""
        font = get_font(FONT_SIZE)
        w = surface.get_width()

        # Background
        line_h = font.get_height() + 2
        total_h = PAD_Y * 2 + line_h
        if self.detail:
            total_h += line_h

        bg = pygame.Rect(0, y, w, total_h)
        pygame.draw.rect(surface, (25, 25, 25), bg)

        # Left accent bar
        accent = pygame.Rect(0, y, ACCENT_W, total_h)
        pygame.draw.rect(surface, self.accent_color, accent)

        # Summary line
        check = font.render("+ ", False, self.accent_color)
        summary_surf = font.render(self.summary[:30], False, WHITE)
        cx = ACCENT_W + PAD_X
        cy = y + PAD_Y
        surface.blit(check, (cx, cy))
        surface.blit(summary_surf, (cx + check.get_width(), cy))

        # Detail line
        if self.detail:
            detail_surf = font.render(self.detail[:36], False, DIM3)
            surface.blit(detail_surf, (cx + check.get_width(), cy + line_h))

        return total_h
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_tool_banner.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add device/ui/components/tool_banner.py tests/test_tool_banner.py
git commit -m "feat: inline tool result banners for chat messages"
```

---

### Task 9: Status Bar Badge Animation

**Files:**
- Modify: `device/ui/components/status_bar.py`
- Test: `tests/test_status_bar_badge.py`

**Step 1: Write the failing test**

```python
# tests/test_status_bar_badge.py
import os
import unittest
import math

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

from device.ui.components.status_bar import StatusBar


class TestStatusBarBadge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_badge_pulse_exists(self):
        sb = StatusBar()
        sb.set_unread_count(3)
        self.assertTrue(hasattr(sb, '_badge_pulse_time'))

    def test_badge_resets_on_zero(self):
        sb = StatusBar()
        sb.set_unread_count(3)
        sb.set_unread_count(0)
        self.assertEqual(sb.unread_count, 0)

    def test_render_with_badge_smoke(self):
        sb = StatusBar()
        sb.set_unread_count(5)
        surf = pygame.Surface((240, 20))
        sb.render(surf, y=0, width=240)  # should not crash

    def test_category_color_stored(self):
        sb = StatusBar()
        sb.set_unread_count(2, category="sms")
        self.assertEqual(sb._badge_color, (60, 130, 220))


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_status_bar_badge.py -v`
Expected: FAIL (no _badge_pulse_time, no category param on set_unread_count)

**Step 3: Update StatusBar**

Add to `StatusBar.__init__`:
```python
self._badge_pulse_time: float = 0.0
self._badge_color: tuple = (255, 255, 255)
```

Update `set_unread_count`:
```python
def set_unread_count(self, count: int, category: str = "") -> None:
    self.unread_count = max(0, count)
    if count > 0:
        self._badge_pulse_time = 0.0  # reset pulse
    if category:
        from device.overlays.notification_banner import CATEGORY_COLORS
        self._badge_color = CATEGORY_COLORS.get(category, (255, 255, 255))
```

Update `render()` badge section to use `_badge_color` and add subtle 0.5Hz alpha pulse:
```python
if self.unread_count > 0:
    self._badge_pulse_time += 1 / 15  # approximate dt
    alpha = int(200 + 55 * math.sin(self._badge_pulse_time * math.pi))
    # Draw badge circle with category color
    ...
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_status_bar_badge.py -v`
Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add device/ui/components/status_bar.py tests/test_status_bar_badge.py
git commit -m "feat: status bar badge with category color and pulse animation"
```

---

### Task 10: Integration — Wire Integrations to Dispatcher

**Files:**
- Modify: `server/main.py` (wire activity feed to dispatcher)
- Create: `server/notifications/integration_bridge.py`

**Step 1: Create integration bridge**

The bridge polls existing endpoints (BlueBubbles, Gmail, Calendar, Vikunja) and funnels new items into the NotificationDispatcher. This replaces the device-side polling for notifications — the device still has the poller as fallback but the primary path is now server→WS→device.

```python
# server/notifications/integration_bridge.py
"""Bridges existing integrations into the NotificationDispatcher."""
from __future__ import annotations

import asyncio
import logging
from .dispatcher import NotificationDispatcher
from .models import NotificationEvent, Priority, CATEGORY_DEFAULTS

log = logging.getLogger(__name__)


class IntegrationBridge:
    """Polls integrations and pushes new items to dispatcher."""

    def __init__(self, dispatcher: NotificationDispatcher, adapters: dict):
        self._dispatcher = dispatcher
        self._adapters = adapters  # {"bluebubbles": adapter, "gmail": adapter, ...}
        self._seen_ids: set[str] = set()

    async def poll_once(self) -> int:
        """Poll all integrations, dispatch new items. Returns count dispatched."""
        count = 0
        for name, adapter in self._adapters.items():
            try:
                items = await self._fetch(name, adapter)
                for item in items:
                    source_id = item.get("source_id", "")
                    key = f"{name}:{source_id}"
                    if key in self._seen_ids:
                        continue
                    self._seen_ids.add(key)
                    if not item.get("unread", True):
                        continue
                    category = self._map_category(name)
                    evt = NotificationEvent(
                        type="notification",
                        priority=CATEGORY_DEFAULTS.get(category, Priority.NORMAL),
                        category=category,
                        payload={
                            "title": item.get("source", name),
                            "body": item.get("preview", "")[:60],
                            "app": name.title(),
                            "source_id": source_id,
                            "icon": self._icon_for(category),
                        },
                    )
                    self._dispatcher.dispatch(evt)
                    count += 1
            except Exception:
                log.exception("Error polling %s", name)
        return count

    async def _fetch(self, name: str, adapter) -> list[dict]:
        if hasattr(adapter, "get_unread"):
            return await adapter.get_unread()
        return []

    @staticmethod
    def _map_category(adapter_name: str) -> str:
        return {
            "bluebubbles": "sms",
            "gmail": "mail",
            "calendar": "calendar",
            "vikunja": "task",
        }.get(adapter_name, "system")

    @staticmethod
    def _icon_for(category: str) -> str:
        return {"sms": "S", "mail": "M", "calendar": "E", "task": "#"}.get(category, "!")
```

**Step 2: Wire into server startup**

In `server/main.py` startup event, create a background task:

```python
@app.on_event("startup")
async def _start_integration_bridge():
    bridge = IntegrationBridge(_notif_dispatcher, {
        "bluebubbles": bluebubbles_adapter,
        "gmail": gmail_adapter,
        "vikunja": vikunja_adapter,
    })
    async def _poll_loop():
        while True:
            await bridge.poll_once()
            await asyncio.sleep(30)
    asyncio.create_task(_poll_loop())
```

**Step 3: Commit**

```bash
git add server/notifications/integration_bridge.py server/main.py
git commit -m "feat: integration bridge funnels SMS/mail/tasks into notification dispatcher"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Server Dispatcher + Queue Store | 7 |
| 2 | WebSocket /ws/device endpoint | 4 |
| 3 | Device NotificationRouter (DND + tiers) | 8 |
| 4 | Animated Banner (progress bar, slide) | 7 |
| 5 | Animated Toast (progress bar, slide) | 4 |
| 6 | Device WS Client (reconnect, replay) | 5 |
| 7 | Wire Router + WS into main.py | manual |
| 8 | In-Chat Tool Result Banners | 5 |
| 9 | Status Bar Badge Animation | 4 |
| 10 | Integration Bridge (SMS/mail/tasks → dispatcher) | manual |

**Total: 10 tasks, ~44 automated tests**
