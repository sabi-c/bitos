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

    def health(self) -> bool:
        """Check if the server is running."""
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=3.0, headers=self._request_headers())
            return r.status_code == 200
        except Exception:
            return False

    def get_ui_settings(self) -> dict:
        """Fetch persisted UI settings from backend."""
        r = httpx.get(f"{self.base_url}/settings/ui", timeout=3.0, headers=self._request_headers())
        r.raise_for_status()
        return r.json()

    def get_settings_catalog(self) -> dict:
        """Fetch editable settings catalog metadata."""
        r = httpx.get(f"{self.base_url}/settings/catalog", timeout=3.0, headers=self._request_headers())
        r.raise_for_status()
        return r.json()

    def update_ui_settings(self, patch: dict) -> dict:
        """Persist a partial UI settings patch."""
        r = httpx.put(f"{self.base_url}/settings/ui", json=patch, timeout=3.0, headers=self._request_headers())
        r.raise_for_status()
        return r.json()

    def chat(self, message: str) -> Generator[str, None, None]:
        """Send a message and yield streamed response chunks."""
        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/chat",
                json={"message": message},
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
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status in (401, 403):
                raise BackendChatError("auth", "Authentication failed", retryable=False) from e
            if status == 429:
                raise BackendChatError("rate_limit", "Rate limited", retryable=True) from e
            if status >= 500:
                raise BackendChatError("upstream", f"Server error {status}", retryable=True) from e
            raise BackendChatError("request", f"Request failed {status}", retryable=False) from e
        except httpx.TimeoutException as e:
            raise BackendChatError("timeout", "Request timed out", retryable=True) from e
        except httpx.ConnectError as e:
            raise BackendChatError("offline", f"Cannot connect to server at {self.base_url}", retryable=True) from e
        except httpx.HTTPError as e:
            raise BackendChatError("network", "Network error", retryable=True) from e
