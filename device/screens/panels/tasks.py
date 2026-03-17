"""Tasks panel backed by server /tasks/today with offline cache.

Shows priority indicators, due dates, subtask counts.
Double-press: first shows detail view, second double-press completes task.
Completion syncs back to server.
"""
from __future__ import annotations

import logging
import threading

import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM2, DIM3, DIM4, HAIRLINE, PHYSICAL_W, PHYSICAL_H, STATUS_BAR_H, ROW_H_MIN
from display.theme import merge_runtime_ui_settings, load_ui_font

logger = logging.getLogger(__name__)

# Priority color indicators (RGB tuples)
PRIORITY_COLORS = {
    1: (220, 60, 60),    # critical — red
    2: (220, 160, 40),   # high — amber
    3: (100, 180, 100),  # normal — green
    4: (120, 120, 160),  # low — grey-blue
}


class TasksPanel(BaseScreen):
    def __init__(self, client, repository, on_back=None, on_task_complete=None, ui_settings: dict | None = None):
        self._client = client
        self._repository = repository
        self._on_back = on_back
        self._on_task_complete = on_task_complete
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._lock = threading.Lock()
        self._cursor = 0
        self._confirm_complete = False
        self._detail_view = False
        self._state = "loading"
        self._tasks: list[dict] = []
        self._load_thread: threading.Thread | None = None

    def on_enter(self):
        self._fetch_tasks()

    def _fetch_tasks(self):
        if self._load_thread and self._load_thread.is_alive():
            return

        def _run():
            try:
                tasks = self._client.get_tasks()
                if tasks:
                    with self._lock:
                        self._tasks = tasks
                        self._state = "ready"
                    self._repository.cache_today_tasks(tasks)
                else:
                    cached = self._repository.get_cached_today_tasks()
                    with self._lock:
                        self._tasks = cached
                        self._state = "empty" if not self._tasks else "offline"
            except Exception:
                cached = self._repository.get_cached_today_tasks()
                with self._lock:
                    self._tasks = cached
                    self._state = "offline"

        self._state = "loading"
        self._load_thread = threading.Thread(target=_run, daemon=True)
        self._load_thread.start()

    def handle_input(self, event: pygame.event.Event):
        _ = event

    def handle_action(self, action: str):
        if action == "LONG_PRESS":
            if self._detail_view:
                # Exit detail view
                with self._lock:
                    self._detail_view = False
                    self._confirm_complete = False
                return
            if self._on_back:
                self._on_back()
            return

        with self._lock:
            if not self._tasks:
                return

            if self._detail_view:
                self._handle_detail_action(action)
                return

            if action == "SHORT_PRESS":
                self._confirm_complete = False
                self._cursor = (self._cursor + 1) % len(self._tasks)
            elif action == "TRIPLE_PRESS":
                self._confirm_complete = False
                self._cursor = (self._cursor - 1) % len(self._tasks)
            elif action == "DOUBLE_PRESS":
                if not self._confirm_complete:
                    # First double-press: show detail view
                    self._detail_view = True
                    self._confirm_complete = False
                    return
                # Second double-press in confirm mode: complete
                self._complete_current_task()

    def _handle_detail_action(self, action: str):
        """Handle actions while in detail view."""
        if action == "DOUBLE_PRESS":
            if not self._confirm_complete:
                self._confirm_complete = True
                return
            self._complete_current_task()
            self._detail_view = False
        elif action == "SHORT_PRESS":
            # Scroll through detail pages (future: paginated notes)
            pass

    def _complete_current_task(self):
        """Mark the current task as complete, sync to server."""
        if 0 <= self._cursor < len(self._tasks):
            task = self._tasks[self._cursor]
            task["done"] = True
            task["status"] = "done"
            task_id = str(task.get("id", ""))
            title = str(task.get("title", "DONE"))

            if self._on_task_complete:
                self._on_task_complete(title)

            # Sync completion to server in background
            if task_id:
                self._sync_complete(task_id)

        self._confirm_complete = False

    def _sync_complete(self, task_id: str):
        """Send completion to server in background thread."""
        def _run():
            try:
                self._client.complete_task(task_id)
                logger.info("task_completed_synced: id=%s", task_id)
            except Exception as exc:
                logger.warning("task_complete_sync_failed: id=%s error=%s", task_id, exc)
                # Queue for retry via outbound command queue
                try:
                    import json
                    self._repository.queue_enqueue_command(
                        domain="tasks",
                        operation="complete",
                        payload=json.dumps({"task_id": task_id}),
                    )
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True).start()

    def _render_skeleton(self, surface, y, count=4):
        from display.skeleton import render_skeleton
        render_skeleton(surface, y, count)

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)
        title = self._font_small.render("TASKS", False, WHITE)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        with self._lock:
            state = self._state
            tasks = list(self._tasks)
            cursor = min(self._cursor, len(tasks) - 1) if tasks else 0
            confirm_complete = self._confirm_complete
            detail_view = self._detail_view

        if state == "loading":
            self._render_skeleton(surface, STATUS_BAR_H + 12)
            return
        if state == "empty":
            s = self._font_body.render("NO TASKS TODAY \u2713", False, DIM2)
            surface.blit(s, ((PHYSICAL_W - s.get_width()) // 2, PHYSICAL_H // 2))
            return
        if state == "offline":
            s = self._font_small.render("OFFLINE \u2014 CACHED DATA", False, DIM3)
            surface.blit(s, ((PHYSICAL_W - s.get_width()) // 2, STATUS_BAR_H + 2))

        if detail_view and 0 <= cursor < len(tasks):
            self._render_detail(surface, tasks[cursor], confirm_complete)
            return

        self._render_list(surface, tasks, cursor, confirm_complete)

    def _render_list(self, surface, tasks, cursor, confirm_complete):
        """Render the task list view with priority indicators and due dates."""
        max_rows = max(1, (PHYSICAL_H - STATUS_BAR_H - 6) // ROW_H_MIN)
        start = min(cursor, max(0, len(tasks) - max_rows))
        y = STATUS_BAR_H + 12

        for idx, task in enumerate(tasks[start: start + max_rows]):
            actual = start + idx
            focused = actual == cursor
            done = task.get("done") or task.get("status") == "done"

            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))

            color = BLACK if focused else WHITE
            dim = BLACK if focused else DIM2

            # Priority indicator dot
            priority = task.get("priority", 3)
            dot_color = PRIORITY_COLORS.get(priority, PRIORITY_COLORS[3])
            if not focused:
                pygame.draw.circle(surface, dot_color, (8, y + ROW_H_MIN // 2), 3)

            # Project and meta line
            project = str(task.get("project", "INBOX"))[:8]
            meta_parts = [project]
            due = task.get("due_date")
            if due:
                meta_parts.append(str(due)[-5:])  # MM-DD
            subtasks = task.get("subtasks", [])
            if subtasks:
                done_count = sum(1 for s in subtasks if s.get("status") == "done")
                meta_parts.append(f"{done_count}/{len(subtasks)}")

            meta_text = " \u00b7 ".join(meta_parts)
            x_offset = 16 if not focused else 4
            indicator = "> " if focused else ""
            surface.blit(
                self._font_small.render(indicator + meta_text, False, dim),
                (x_offset, y + 2),
            )

            # Title (strikethrough if done)
            title_text = str(task.get("title", ""))[:24]
            if done:
                title_text = "\u2713 " + title_text
            surface.blit(
                self._font_body.render(title_text, False, DIM3 if done else color),
                (x_offset, y + self._font_small.get_height() + 4),
            )

            y += ROW_H_MIN

        if confirm_complete:
            hint = self._font_small.render("DBL AGAIN TO COMPLETE", False, DIM2)
            surface.blit(hint, (6, PHYSICAL_H - 16))

    def _render_detail(self, surface, task, confirm_complete):
        """Render the detail view for a single task."""
        y = STATUS_BAR_H + 8

        # Priority badge
        priority = task.get("priority", 3)
        prio_labels = {1: "CRITICAL", 2: "HIGH", 3: "NORMAL", 4: "LOW"}
        prio_color = PRIORITY_COLORS.get(priority, PRIORITY_COLORS[3])
        prio_text = prio_labels.get(priority, "NORMAL")
        surface.blit(self._font_small.render(prio_text, False, prio_color), (6, y))
        y += 14

        # Title
        title = str(task.get("title", ""))
        # Word-wrap title to ~28 chars per line
        for i in range(0, len(title), 28):
            line = title[i:i + 28]
            surface.blit(self._font_body.render(line, False, WHITE), (6, y))
            y += self._font_body.get_height() + 2
        y += 4

        # Due date
        due = task.get("due_date")
        if due:
            surface.blit(self._font_small.render(f"Due: {due}", False, DIM2), (6, y))
            y += 14

        # Project
        project = task.get("project", "INBOX")
        surface.blit(self._font_small.render(f"Project: {project}", False, DIM2), (6, y))
        y += 14

        # Notes (truncated)
        notes = str(task.get("notes", ""))[:120]
        if notes:
            y += 4
            for i in range(0, len(notes), 32):
                line = notes[i:i + 32]
                surface.blit(self._font_small.render(line, False, DIM3), (6, y))
                y += 12
                if y > PHYSICAL_H - 30:
                    break

        # Subtasks
        subtasks = task.get("subtasks", [])
        if subtasks:
            y += 6
            surface.blit(self._font_small.render("SUBTASKS:", False, DIM2), (6, y))
            y += 12
            for sub in subtasks[:5]:
                done = sub.get("status") == "done"
                mark = "\u2713" if done else "\u2022"
                sub_title = str(sub.get("title", ""))[:26]
                surface.blit(
                    self._font_small.render(f" {mark} {sub_title}", False, DIM3 if done else DIM2),
                    (6, y),
                )
                y += 12

        # Footer hint
        if confirm_complete:
            hint = self._font_small.render("DBL AGAIN TO COMPLETE", False, DIM2)
        else:
            hint = self._font_small.render("DBL=complete  LONG=back", False, DIM4)
        surface.blit(hint, (6, PHYSICAL_H - 16))
