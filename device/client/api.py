"""
BITOS Backend Client
HTTP client for communicating with the FastAPI server.
"""
import os
import json
from typing import Generator

import httpx


DEFAULT_SERVER_URL = "http://localhost:8000"


class BackendClient:
    """HTTP client to the Bitos backend."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.environ.get("BITOS_SERVER_URL", DEFAULT_SERVER_URL)

    def health(self) -> bool:
        """Check if the server is running."""
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False

    def chat(self, message: str) -> Generator[str, None, None]:
        """Send a message and yield streamed response chunks."""
        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/chat",
                json={"message": message},
                timeout=60.0,
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
            raise RuntimeError(f"Server error: {e.response.status_code}") from e
        except httpx.ConnectError:
            raise RuntimeError(f"Cannot connect to server at {self.base_url}")
