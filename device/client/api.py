"""
BITOS Backend Client
HTTP client for communicating with the FastAPI server.
"""
import logging
import os
import json
from typing import Generator

import httpx


DEFAULT_SERVER_URL = "http://localhost:8000"


class BackendChatError(RuntimeError):
    """Normalized chat error surfaced to UI for tiny-screen friendly messaging."""

    def __init__(self, kind: str, message: str, retryable: bool = True):
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable


class BackendClient:
    """HTTP client to the Bitos backend."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.environ.get("BITOS_SERVER_URL", DEFAULT_SERVER_URL)
        self.device_token = os.environ.get("BITOS_DEVICE_TOKEN", "")
        if not self.device_token:
            logging.warning("[BITOS] BITOS_DEVICE_TOKEN is not set; running in dev mode without device token auth")

    def _request_headers(self) -> dict:
        if not self.device_token:
            return {}
        return {"X-Device-Token": self.device_token}

    @staticmethod
    def _http_error_message(exc: Exception) -> tuple[str, str]:
        if isinstance(exc, httpx.ConnectError):
            return "offline", "Server offline"
        if isinstance(exc, httpx.TimeoutException):
            return "timeout", "Server timeout"
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code if exc.response is not None else 500
            return "server", f"Server error {status}"
        return "network", "Server error 500"

    def health(self, timeout: float = 3.0) -> bool:
        """Check if the server is running."""
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=timeout, headers=self._request_headers())
            return r.status_code == 200
        except Exception as exc:
            logging.warning("backend_health_failed error=%s", exc)
            return False

    def get_ui_settings(self) -> dict:
        """Fetch persisted UI settings from backend."""
        try:
            r = httpx.get(f"{self.base_url}/settings/ui", timeout=3.0, headers=self._request_headers())
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            _kind, message = self._http_error_message(exc)
            raise RuntimeError(message) from exc

    def get_settings_catalog(self) -> dict:
        """Fetch editable settings catalog metadata."""
        try:
            r = httpx.get(f"{self.base_url}/settings/catalog", timeout=3.0, headers=self._request_headers())
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            _kind, message = self._http_error_message(exc)
            raise RuntimeError(message) from exc

    def update_ui_settings(self, patch: dict) -> dict:
        """Persist a partial UI settings patch."""
        try:
            r = httpx.put(f"{self.base_url}/settings/ui", json=patch, timeout=3.0, headers=self._request_headers())
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            _kind, message = self._http_error_message(exc)
            raise RuntimeError(message) from exc

    def chat(self, message: str) -> Generator[str, None, None] | dict:
        """Send a message and yield chunks as they stream from SSE."""
        from power import BatteryMonitor
        from storage.repository import DeviceRepository

        mode = "producer"
        tasks_today: list[str] = []
        battery_pct: int | None = None
        web_search = True
        memory = True
        ai_model = ""

        try:
            repository = DeviceRepository()
            mode = str(repository.get_setting("agent_mode", "producer"))
            web_search = bool(repository.get_setting("web_search", True))
            memory = bool(repository.get_setting("memory", True))
            ai_model = str(repository.get_setting("ai_model", "") or "")
            tasks_today = [str(t.get("title", "")).strip() for t in repository.list_incomplete_tasks(limit=3)]
            tasks_today = [t for t in tasks_today if t]
        except Exception as exc:
            logging.debug("chat_context_load_failed error=%s", exc)

        try:
            battery_pct = int(BatteryMonitor().get_status().get("pct"))
        except Exception as exc:
            logging.debug("battery_read_failed error=%s", exc)

        try:
            return self._stream_chat_sse(message, mode, tasks_today, battery_pct, web_search, memory, ai_model)
        except Exception as exc:
            kind, message_copy = self._http_error_message(exc)
            retryable = kind in {"offline", "timeout", "network", "server"}
            return {"error": message_copy, "kind": kind, "retryable": retryable}

    def _stream_chat_sse(
        self,
        message: str,
        mode: str,
        tasks_today: list[str],
        battery_pct: int | None,
        web_search: bool = True,
        memory: bool = True,
        model: str = "",
    ) -> Generator[str, None, None]:
        """Yield text chunks from the /chat SSE stream in real time."""
        payload: dict = {
            "message": message,
            "agent_mode": mode,
            "tasks_today": tasks_today,
            "battery_pct": battery_pct,
            "web_search": web_search,
            "memory": memory,
            "response_format_hint": (
                "Keep responses concise and structured. Use short paragraphs "
                "separated by blank lines. Aim for under 800 characters total "
                "— the device displays text in pages of ~250 characters each."
            ),
        }
        if model:
            payload["model"] = model
        with httpx.stream(
            "POST",
            f"{self.base_url}/chat",
            json=payload,
            timeout=60.0,
            headers=self._request_headers(),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if "text" in chunk:
                            yield chunk["text"]
                    except json.JSONDecodeError:
                        yield data


    def get_integration_status(self) -> dict:
        """GET /status/integrations."""
        try:
            resp = httpx.get(f"{self.base_url}/status/integrations", timeout=5, headers=self._request_headers())
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logging.warning("integration_status_failed error=%s", exc)
            return {}

    def get_conversations(self) -> list[dict]:
        """GET /messages and return conversations list."""
        try:
            resp = httpx.get(f"{self.base_url}/messages", timeout=5, headers=self._request_headers())
            resp.raise_for_status()
            return resp.json().get("conversations", [])
        except Exception as exc:
            logging.warning("messages_conversations_failed error=%s", exc)
            return []

    def get_messages(self, chat_id: str) -> list[dict]:
        """GET /messages/{chat_id} and return thread messages."""
        try:
            resp = httpx.get(f"{self.base_url}/messages/{chat_id}", timeout=5, headers=self._request_headers())
            resp.raise_for_status()
            return resp.json().get("messages", [])
        except Exception as exc:
            logging.warning("messages_thread_failed chat=%s error=%s", chat_id[:24], exc)
            return []

    def draft_reply(self, chat_id: str, transcript: str) -> str:
        """POST /messages/draft and return generated draft text."""
        try:
            resp = httpx.post(
                f"{self.base_url}/messages/draft",
                json={"chat_id": chat_id, "voice_transcript": transcript},
                timeout=30,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            return str(resp.json().get("draft", "")).strip()
        except Exception as exc:
            logging.warning("messages_draft_failed chat=%s error=%s", chat_id[:24], exc)
            return ""

    def send_message(self, chat_id: str, text: str, confirmed=False) -> bool:
        """POST /messages/send and return sent status."""
        try:
            resp = httpx.post(
                f"{self.base_url}/messages/send",
                json={"chat_id": chat_id, "text": text, "confirmed": bool(confirmed)},
                timeout=10,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            return bool(resp.json().get("sent", False))
        except Exception as exc:
            logging.warning("messages_send_failed chat=%s error=%s", chat_id[:24], exc)
            return False


    def get_mail_inbox(self) -> list[dict]:
        """GET /mail and return mail thread summaries."""
        try:
            resp = httpx.get(f"{self.base_url}/mail", timeout=5, headers=self._request_headers())
            resp.raise_for_status()
            return resp.json().get("threads", [])
        except Exception as exc:
            logging.warning("mail_inbox_failed error=%s", exc)
            return []

    def get_mail_thread(self, thread_id: str) -> list[dict]:
        """GET /mail/{thread_id} and return full thread messages."""
        try:
            resp = httpx.get(f"{self.base_url}/mail/{thread_id}", timeout=5, headers=self._request_headers())
            resp.raise_for_status()
            return resp.json().get("messages", [])
        except Exception as exc:
            logging.warning("mail_thread_failed thread=%s error=%s", thread_id[:24], exc)
            return []

    def draft_mail_reply(self, thread_id: str, transcript: str) -> str:
        """POST /mail/draft and return generated draft text."""
        try:
            resp = httpx.post(
                f"{self.base_url}/mail/draft",
                json={"thread_id": thread_id, "voice_transcript": transcript},
                timeout=30,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            return str(resp.json().get("draft", "")).strip()
        except Exception as exc:
            logging.warning("mail_draft_failed thread=%s error=%s", thread_id[:24], exc)
            return ""

    def create_mail_draft(self, thread_id: str, body: str, confirmed=False) -> str:
        """POST /mail/create-draft and return created draft id."""
        try:
            resp = httpx.post(
                f"{self.base_url}/mail/create-draft",
                json={"thread_id": thread_id, "body": body, "confirmed": bool(confirmed)},
                timeout=10,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            return str(resp.json().get("draft_id", "")).strip()
        except Exception as exc:
            logging.warning("mail_create_draft_failed thread=%s error=%s", thread_id[:24], exc)
            return ""

    def get_tasks(self) -> list[dict]:
        """GET /tasks/today from server."""
        try:
            resp = httpx.get(
                f"{self.base_url}/tasks/today",
                timeout=5,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            return resp.json().get("tasks", [])
        except Exception as exc:
            logging.warning("tasks_fetch_failed error=%s", exc)
            return []


    def get_device_stats(self) -> dict:
        """GET /device/stats from server."""
        try:
            resp = httpx.get(f"{self.base_url}/device/stats", timeout=5, headers=self._request_headers())
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logging.warning("device_stats_failed error=%s", exc)
            return {}

    def get_morning_brief(self) -> dict:
        """GET /brief from server."""
        try:
            resp = httpx.get(f"{self.base_url}/brief", timeout=5, headers=self._request_headers())
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logging.warning("morning_brief_failed error=%s", exc)
            return {}

    def get_agent_subtasks(self, status: str | None = None) -> list[dict]:
        """GET /agent/subtasks with optional status filter."""
        try:
            params = {"status": status} if status else {}
            resp = httpx.get(
                f"{self.base_url}/agent/subtasks",
                params=params,
                timeout=5,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            return resp.json().get("subtasks", [])
        except Exception as exc:
            logging.warning("agent_subtasks_failed error=%s", exc)
            return []

    def submit_agent_subtask(self, name: str, prompt: str) -> str:
        """POST /agent/subtasks, returns task_id."""
        try:
            resp = httpx.post(
                f"{self.base_url}/agent/subtasks",
                json={"name": name, "prompt": prompt},
                timeout=10,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            return resp.json().get("task_id", "")
        except Exception as exc:
            logging.warning("agent_subtask_submit_failed error=%s", exc)
            return ""

    def get_agent_subtask(self, task_id: str) -> dict:
        """GET /agent/subtasks/{task_id}."""
        try:
            resp = httpx.get(
                f"{self.base_url}/agent/subtasks/{task_id}",
                timeout=5,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logging.warning("agent_subtask_detail_failed task=%s error=%s", task_id[:12], exc)
            return {}
