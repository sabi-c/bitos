"""Background pull-based notification sources."""
from __future__ import annotations

import threading
import time
import uuid
from datetime import date

from overlays.notification import NotificationQueue, NotificationRecord


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
        self._notified_subtask_ids: set[str] = set()

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
        while not self._stop.wait(1.0):
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
