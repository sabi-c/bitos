"""Background pull-based notification sources."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import date

from overlays.notification import NotificationQueue, NotificationRecord

logger = logging.getLogger(__name__)


class NotificationPoller:
    def __init__(self, queue: NotificationQueue, api_client, repository):
        self._queue = queue
        self._api_client = api_client
        self._repository = repository
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_health_state: bool | None = None
        self._notified_overdue_task_ids: set[str] = set()
        # Optional callback for interactive banners (set by main.py)
        self.on_banner: callable | None = None
        self._notified_activity_ids: set[str] = set()
        self._notified_subtask_ids: set[str] = set()
        self._update_notified = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="notification-poller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

    def _poll_loop(self) -> None:
        next_health_poll = 0.0
        next_task_poll = 0.0
        next_subtask_poll = 0.0
        next_update_poll = 15.0  # Check for updates 15s after boot
        next_settings_poll = 5.0  # Check for companion app setting changes
        next_activity_poll = 10.0  # Check activity feed 10s after boot
        consecutive_errors = 0
        while not self._stop.wait(1.0):
            try:
                now = time.time()
                if now >= next_health_poll:
                    self._poll_health_state()
                    next_health_poll = now + 30.0
                if now >= next_task_poll:
                    self._poll_overdue_tasks()
                    next_task_poll = now + 300.0
                if now >= next_subtask_poll:
                    self._poll_completed_subtasks()
                    next_subtask_poll = now + 10.0
                if now >= next_update_poll:
                    self._poll_update_available()
                    next_update_poll = now + 3600.0  # Re-check hourly
                if now >= next_settings_poll:
                    self._poll_pending_settings()
                    next_settings_poll = now + 5.0  # Check every 5s
                if now >= next_activity_poll:
                    self._poll_activity_feed()
                    next_activity_poll = now + 30.0  # Check every 30s
                consecutive_errors = 0
            except Exception as exc:
                consecutive_errors += 1
                logger.error("poll_loop_error count=%d error=%s", consecutive_errors, exc)
                # Back off on repeated failures to avoid log spam
                if consecutive_errors > 5:
                    self._stop.wait(min(30, consecutive_errors * 2))

    def _poll_health_state(self) -> None:
        state = bool(self._api_client.health())
        if self._last_health_state is None:
            self._last_health_state = state
            return
        if state == self._last_health_state:
            return

        self._last_health_state = state
        message = "AI back online" if state else "AI went offline"
        record = NotificationRecord(
            id=f"health:{uuid.uuid4().hex}",
            type="CLAUDE",
            app_name="CLAUDE",
            message=message,
            time_str=time.strftime("%H:%M"),
            source_id="health",
        )
        self._queue.push_record(record)
        # Show interactive banner for AI status changes
        if self.on_banner:
            self.on_banner("CLAUDE", "C", message)

    def _poll_overdue_tasks(self) -> None:
        overdue = self._repository.list_overdue_tasks(date.today().isoformat())
        for row in overdue:
            task_id = str(row["id"])
            if task_id in self._notified_overdue_task_ids:
                continue
            self._notified_overdue_task_ids.add(task_id)
            title = str(row["title"])
            record = NotificationRecord(
                id=f"task:{task_id}:{uuid.uuid4().hex}",
                type="TASK",
                app_name="TASKS",
                message=f"{title} — overdue",
                time_str=time.strftime("%H:%M"),
                source_id=task_id,
            )
            self._queue.push_record(record)

    def _poll_update_available(self) -> None:
        """Check server for available OTA updates."""
        if self._update_notified:
            return
        try:
            info = self._api_client.get_device_version()
        except Exception:
            return
        if not info.get("update_available"):
            return

        behind = info.get("behind", 0)
        self._update_notified = True
        message = f"Update ready ({behind} commit{'s' if behind != 1 else ''} behind)"
        record = NotificationRecord(
            id=f"update:{uuid.uuid4().hex}",
            type="CLAUDE",
            app_name="SYSTEM",
            message=message,
            time_str=time.strftime("%H:%M"),
            source_id="update",
        )
        self._queue.push_record(record)
        if self.on_banner:
            self.on_banner("SYSTEM", "S", message)

    def _poll_pending_settings(self) -> None:
        """Check server for pending setting changes from companion app."""
        try:
            resp = self._api_client._request_headers  # verify client has the method
            import httpx
            resp = httpx.get(
                f"{self._api_client.base_url}/settings/device/pending",
                timeout=5,
                headers=self._api_client._request_headers(),
            )
            resp.raise_for_status()
            changes = resp.json().get("changes", [])
            for change in changes:
                self._api_client._apply_setting_change(change)
        except Exception:
            pass  # Non-critical — will retry next cycle

    def _poll_completed_subtasks(self) -> None:
        if not hasattr(self._api_client, "get_agent_subtasks"):
            return
        try:
            subtasks = self._api_client.get_agent_subtasks(status="complete")
        except Exception:
            return
        for task in subtasks:
            task_id = str(task.get("id", ""))
            if not task_id or task_id in self._notified_subtask_ids:
                continue
            self._notified_subtask_ids.add(task_id)
            name = str(task.get("name", "subtask"))
            cost = task.get("cost_usd", 0.0)
            record = NotificationRecord(
                id=f"subtask:{task_id}:{uuid.uuid4().hex}",
                type="TASK",
                app_name="Agent",
                message=f"{name} \u2713 ${cost:.3f}",
                time_str=time.strftime("%H:%M"),
                source_id=task_id,
            )
            self._queue.push_record(record)

    def _poll_activity_feed(self) -> None:
        """Poll /activity for new unread messages, emails, and calendar events."""
        try:
            import httpx
            resp = httpx.get(
                f"{self._api_client.base_url}/activity",
                timeout=10,
                headers=self._api_client._request_headers(),
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except Exception:
            return

        _TYPE_ICON = {"SMS": "S", "MAIL": "M", "CALENDAR": "E", "TASK": "#"}

        for item in items:
            item_type = item.get("type", "SMS")
            source_id = item.get("source_id", "")
            dedup_key = f"{item_type}:{source_id or item.get('source', '')}"
            if dedup_key in self._notified_activity_ids:
                continue
            if not item.get("unread", False):
                continue

            self._notified_activity_ids.add(dedup_key)
            source = item.get("source", "")[:12]
            preview = item.get("preview", "")[:24]

            record = NotificationRecord(
                id=f"activity:{dedup_key}:{uuid.uuid4().hex[:6]}",
                type=item_type if item_type in ("SMS", "MAIL", "CALENDAR", "TASK") else "SMS",
                app_name=source,
                message=preview,
                time_str=str(item.get("time", ""))[:5] or time.strftime("%H:%M"),
                source_id=source_id,
            )
            self._queue.push_record(record)

            if item_type in ("SMS", "MAIL") and self.on_banner:
                icon = _TYPE_ICON.get(item_type, "N")
                self.on_banner(source, icon, preview)
