"""Vikunja task provider adapter for BITOS.

Connects to a Vikunja (https://vikunja.io) instance for task management.
Falls back to a no-op mock when VIKUNJA_API_TOKEN is not set.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)


class VikunjaAdapter:
    """Vikunja REST API adapter for task CRUD.

    Env vars:
        VIKUNJA_BASE_URL  — e.g. https://tasks.example.com/api/v1
        VIKUNJA_API_TOKEN — personal API token (empty = mock mode)
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
    ):
        self._base_url = (base_url or os.environ.get("VIKUNJA_BASE_URL", "")).rstrip("/")
        self._token = api_token or os.environ.get("VIKUNJA_API_TOKEN", "")
        self._mock = not bool(self._token)
        if self._mock:
            logger.info("vikunja_adapter mock_mode=true (no VIKUNJA_API_TOKEN)")

    @property
    def is_mock(self) -> bool:
        return self._mock

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def list_tasks(self, project_id: int | None = None) -> list[dict]:
        """List tasks, optionally filtered by project."""
        if self._mock:
            return []
        url = f"{self._base_url}/tasks"
        params: dict[str, str] = {}
        if project_id is not None:
            url = f"{self._base_url}/projects/{project_id}/tasks"
        try:
            resp = httpx.get(url, headers=self._headers(), params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("vikunja_list_tasks_failed error=%s", exc)
            return []

    def create_task(self, title: str, project_id: int = 1, details: str | None = None) -> dict | None:
        """Create a task. Returns the created task dict or None on failure."""
        if self._mock:
            logger.info("vikunja_mock create_task title=%s", title[:32])
            return {"id": 0, "title": title, "mock": True}
        body: dict[str, object] = {"title": title}
        if details:
            body["description"] = details
        try:
            resp = httpx.put(
                f"{self._base_url}/projects/{project_id}/tasks",
                headers=self._headers(),
                json=body,
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("vikunja_create_task_failed error=%s", exc)
            return None

    def complete_task(self, task_id: int) -> bool:
        """Mark a task as done."""
        if self._mock:
            logger.info("vikunja_mock complete_task id=%s", task_id)
            return True
        try:
            resp = httpx.post(
                f"{self._base_url}/tasks/{task_id}",
                headers=self._headers(),
                json={"done": True},
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("vikunja_complete_task_failed error=%s", exc)
            return False

    def get_tasks_today(self) -> list[str]:
        """Return today's task titles for system prompt injection."""
        tasks = self.list_tasks()
        return [t.get("title", "") for t in tasks if not t.get("done") and t.get("title")][:5]
