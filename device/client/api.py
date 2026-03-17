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
        self.on_approval_request = None  # Callable[[str, str, list[str]], None] or None
        self.on_test_typewriter: callable | None = None
        self.on_volume_change: callable | None = None  # Callable[[int], None] or None
        self._conversation_id: str | None = None  # Multi-turn conversation tracking
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
            if status == 401:
                return "auth", "Auth failed"
            if status == 429:
                return "rate_limit", "Rate limited"
            if status == 502:
                return "upstream", "AI unavailable"
            if status == 503:
                return "upstream", "Server busy"
            return "server", f"Server error {status}"
        return "network", "Network error"

    def post(self, path: str, json: dict | None = None, timeout: float = 5.0) -> httpx.Response:
        """Generic POST helper for endpoints without dedicated methods."""
        return httpx.post(
            f"{self.base_url}{path}",
            json=json or {},
            timeout=timeout,
            headers=self._request_headers(),
        )

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
        location: dict | None = None
        web_search = True
        memory = True
        ai_model = ""
        volume = 100
        voice_enabled = False
        voice_mode = "auto"
        extended_thinking = False
        meta_prompt = ""

        try:
            repository = DeviceRepository()
            mode = str(repository.get_setting("agent_mode", "producer"))
            web_search = bool(repository.get_setting("web_search", True))
            memory = bool(repository.get_setting("memory", True))
            ai_model = str(repository.get_setting("ai_model", "") or "")
            volume = repository.get_setting("volume", 100)
            voice_enabled = repository.get_setting("voice_enabled", False)
            voice_mode = str(repository.get_setting("voice_mode", "auto"))
            extended_thinking = bool(repository.get_setting("extended_thinking", False))
            meta_prompt = str(repository.get_setting("meta_prompt", "") or "")
            tasks_today = [str(t.get("title", "")).strip() for t in repository.list_incomplete_tasks(limit=3)]
            tasks_today = [t for t in tasks_today if t]
            # Load cached geolocation if available
            import json as _json
            raw_loc = repository.get_setting("geolocation", default=None)
            if raw_loc:
                location = _json.loads(raw_loc) if isinstance(raw_loc, str) else raw_loc
        except Exception as exc:
            logging.debug("chat_context_load_failed error=%s", exc)

        try:
            raw_pct = BatteryMonitor().get_status().get("pct")
            battery_pct = int(raw_pct) if raw_pct is not None else None
        except Exception as exc:
            logging.debug("battery_read_failed error=%s", exc)

        try:
            gen = self._stream_chat_sse(message, mode, tasks_today, battery_pct, web_search, memory, ai_model, location, volume, voice_enabled, voice_mode, extended_thinking, meta_prompt)
            # Eagerly start the generator so connection errors are caught here
            first = next(gen)
        except StopIteration:
            return iter([])  # type: ignore[return-value]
        except Exception as exc:
            kind, message_copy = self._http_error_message(exc)
            retryable = kind in {"offline", "timeout", "network", "server"}
            return {"error": message_copy, "kind": kind, "retryable": retryable}

        import itertools
        return itertools.chain([first], gen)

    def _stream_chat_sse(
        self,
        message: str,
        mode: str,
        tasks_today: list[str],
        battery_pct: int | None,
        web_search: bool = True,
        memory: bool = True,
        model: str = "",
        location: dict | None = None,
        volume: int = 100,
        voice_enabled: bool = False,
        voice_mode: str = "auto",
        extended_thinking: bool = False,
        meta_prompt: str = "",
    ) -> Generator[str, None, None]:
        """Yield text chunks from the /chat SSE stream in real time."""
        payload: dict = {
            "message": message,
            "agent_mode": mode,
            "tasks_today": tasks_today,
            "battery_pct": battery_pct,
            "web_search": web_search,
            "extended_thinking": extended_thinking,
            "memory": memory,
            "volume": volume,
            "voice_enabled": voice_enabled,
            "response_format_hint": (
                "Keep responses concise and structured. Use short paragraphs "
                "separated by blank lines. Aim for under 800 characters total "
                "— the device displays text in pages of ~250 characters each. "
                "Device commands (parsed out before display): "
                "{{volume:NUMBER}} (0-100) to set volume, "
                "{{voice:on}} or {{voice:off}} to toggle voice replies. "
                "Current volume: " + str(volume) + "%. "
                "Voice: " + (
                    "FORCED OFF by user — do not use voice commands" if voice_mode == "off"
                    else "FORCED ON by user" if voice_mode == "on"
                    else ("ON" if voice_enabled else "OFF (available — user can ask you to turn it on)")
                ) + "."
            ),
        }
        if model:
            payload["model"] = model
        if location:
            payload["location"] = location
        if meta_prompt:
            payload["meta_prompt"] = meta_prompt
        # Multi-turn: send conversation_id if we have one from a previous exchange
        if self._conversation_id:
            payload["conversation_id"] = self._conversation_id
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
                        elif "setting_change" in chunk:
                            # Agent requested a setting change — apply it
                            self._apply_setting_change(chunk["setting_change"])
                        elif "approval_request" in chunk:
                            # Agent wants user approval — show overlay
                            self._handle_approval_request(chunk["approval_request"])
                        elif "conversation_id" in chunk:
                            # Server assigned/confirmed conversation_id for multi-turn
                            self._conversation_id = chunk["conversation_id"]
                            logging.debug("conversation_id: %s", self._conversation_id)
                        elif "perception" in chunk:
                            # Perception metadata — log but don't yield as text
                            logging.debug("perception: %s", chunk["perception"])
                    except json.JSONDecodeError:
                        yield data


    def new_conversation(self) -> None:
        """Reset conversation state so the next chat() starts a fresh conversation."""
        self._conversation_id = None

    @property
    def conversation_id(self) -> str | None:
        """Return the current multi-turn conversation ID, if any."""
        return self._conversation_id

    def _handle_approval_request(self, data: dict) -> None:
        """Handle an approval_request SSE event from the agent."""
        request_id = data.get("id", "")
        prompt = data.get("prompt", "Confirm?")
        options = data.get("options", ["Yes", "No"])
        logging.info("approval_request: id=%s prompt=%s", request_id, prompt)

        if self.on_approval_request:
            # Show the overlay — main.py wires this up
            self.on_approval_request(request_id, prompt, options)

    def submit_approval(self, request_id: str, choice: str) -> bool:
        """POST /chat/approval — submit user's choice for a blocking approval."""
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/approval",
                json={"request_id": request_id, "choice": choice},
                timeout=10,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            return bool(resp.json().get("ok"))
        except Exception as exc:
            logging.warning("approval_submit_failed: id=%s error=%s", request_id, exc)
            return False

    def _apply_setting_change(self, change: dict) -> None:
        """Apply a setting change requested by the agent."""
        key = change.get("key", "")
        value = change.get("value")
        if not key:
            return

        # Test commands (prefixed with _) — not persisted
        if key == "_test_voice":
            self._handle_test_voice(value)
            return
        if key == "_test_typewriter":
            self._handle_test_typewriter(value)
            return

        try:
            from storage.repository import DeviceRepository
            repo = DeviceRepository()
            repo.set_setting(key, value)
            logging.info("agent_setting_applied: %s=%s", key, value)

            # For volume changes, also update ALSA immediately + show HUD
            if key == "volume":
                from audio.player import AudioPlayer
                player = AudioPlayer()
                vol_int = max(0, min(100, int(value)))
                player.set_volume(vol_int / 100.0)
                if self.on_volume_change:
                    self.on_volume_change(vol_int)

            # Re-init TTS when voice settings change
            if key in ("tts_engine", "voice_id", "voice_params"):
                # The next speak() call will pick up new settings via TextToSpeech()
                logging.info("voice_setting_changed: %s — TTS will reload on next speak", key)
        except Exception as exc:
            logging.warning("agent_setting_apply_failed: key=%s error=%s", key, exc)

    def _handle_test_voice(self, value: str) -> None:
        """Play a voice test with specified engine/voice/params."""
        import json
        try:
            data = json.loads(value) if isinstance(value, str) else value
            text = data.get("text", "Hello!")
            engine = data.get("engine", "auto")
            voice_id = data.get("voice_id", "")
            params = data.get("params", {})

            from storage.repository import DeviceRepository
            repo = DeviceRepository()
            # Temporarily set voice settings for this test
            if engine and engine != "auto":
                repo.set_setting("tts_engine", engine)
            if voice_id:
                repo.set_setting("voice_id", voice_id)
            if params:
                repo.set_setting("voice_params", json.dumps(params))

            from audio.tts import TextToSpeech
            tts = TextToSpeech()
            tts.speak(text)
        except Exception as exc:
            logging.warning("test_voice_failed: %s", exc)

    def _handle_test_typewriter(self, value: str) -> None:
        """Trigger a typewriter test overlay on the device."""
        import json
        try:
            data = json.loads(value) if isinstance(value, str) else value
            if self.on_test_typewriter:
                self.on_test_typewriter(data.get("text", "Test"), data.get("config", {}))
        except Exception as exc:
            logging.warning("test_typewriter_failed: %s", exc)

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

    def get_task(self, task_id: str) -> dict | None:
        """GET /tasks/{id} — get single task with subtasks."""
        try:
            resp = httpx.get(
                f"{self.base_url}/tasks/{task_id}",
                timeout=5,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logging.warning("task_detail_failed id=%s error=%s", task_id[:12], exc)
            return None

    def complete_task(self, task_id: str) -> bool:
        """POST /tasks/{id}/complete — mark task done on server."""
        try:
            resp = httpx.post(
                f"{self.base_url}/tasks/{task_id}/complete",
                timeout=5,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logging.warning("task_complete_failed id=%s error=%s", task_id[:12], exc)
            return False

    def get_activity(self, category: str | None = None) -> list[dict]:
        """GET /activity — unified activity feed."""
        try:
            params = {}
            if category and category != "ALL":
                params["type"] = category
            resp = httpx.get(
                f"{self.base_url}/activity",
                params=params,
                timeout=5,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else data.get("items", [])
        except Exception as exc:
            logging.warning("activity_fetch_failed error=%s", exc)
            return []

    def mark_activity_read(self, item_id: str) -> bool:
        """POST /activity/{id}/read — mark feed item as read."""
        try:
            resp = httpx.post(
                f"{self.base_url}/activity/{item_id}/read",
                json={},
                timeout=3,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logging.warning("activity_mark_read_failed error=%s", exc)
            return False

    def get_device_version(self) -> dict:
        """GET /device/version — check for updates."""
        try:
            resp = httpx.get(f"{self.base_url}/device/version", timeout=10, headers=self._request_headers())
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logging.warning("device_version_failed error=%s", exc)
            return {}

    def trigger_update(self) -> dict:
        """POST /device/update — trigger OTA update."""
        try:
            resp = httpx.post(
                f"{self.base_url}/device/update",
                json={"confirmed": True},
                timeout=30,
                headers=self._request_headers(),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logging.warning("device_update_failed error=%s", exc)
            return {"ok": False, "error": str(exc)}

    def get_device_stats(self) -> dict:
        """GET /device/stats from server."""
        try:
            resp = httpx.get(f"{self.base_url}/device/stats", timeout=5, headers=self._request_headers())
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logging.warning("device_stats_failed error=%s", exc)
            return {}

    def get_files(self, path: str = "") -> list[dict]:
        """GET /files — list files in curated file system."""
        try:
            params = {"path": path} if path else {}
            resp = httpx.get(f"{self.base_url}/files", params=params, timeout=5, headers=self._request_headers())
            resp.raise_for_status()
            return resp.json().get("files", [])
        except Exception as exc:
            logging.warning("files_list_failed error=%s", exc)
            return []

    def get_file_content(self, file_id: str) -> dict:
        """GET /files/{file_id} — get file content."""
        try:
            resp = httpx.get(f"{self.base_url}/files/{file_id}", timeout=5, headers=self._request_headers())
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logging.warning("file_content_failed file=%s error=%s", file_id[:24], exc)
            return {}

    def parse_file(self, file_id: str) -> dict:
        """POST /files/{file_id}/parse — parse file into device-friendly pages."""
        try:
            resp = httpx.post(f"{self.base_url}/files/{file_id}/parse", timeout=30, headers=self._request_headers())
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logging.warning("file_parse_failed file=%s error=%s", file_id[:24], exc)
            return {}

    def get_context(self) -> dict:
        """GET /context — aggregated live context for home screen ticker."""
        try:
            resp = httpx.get(f"{self.base_url}/context", timeout=10, headers=self._request_headers())
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logging.warning("context_fetch_failed error=%s", exc)
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
