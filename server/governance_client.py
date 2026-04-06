"""HTTP client for governance-engine's /agent/chat endpoint."""
from __future__ import annotations

import json
import logging
import os
from typing import Generator

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_URL = "http://localhost:8100"
_TIMEOUT = 120.0


class GovernanceClient:
    """Client for governance-engine's streaming chat API."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.environ.get("GOVERNANCE_URL", _DEFAULT_URL)
        self.last_conversation_id: str | None = None

    def chat_stream(
        self,
        message: str,
        chat_id: str = "bitos",
        conversation_id: str | None = None,
        is_voice: bool = False,
        device_context: dict | None = None,
    ) -> Generator[str | dict, None, None]:
        """Stream chat response from governance-engine.

        Yields:
            str — text chunks for display/TTS
            dict — special events like {"tool_status": "..."}
        """
        payload = {
            "message": message,
            "chat_id": chat_id,
            "is_voice": is_voice,
        }
        if conversation_id or self.last_conversation_id:
            payload["conversation_id"] = conversation_id or self.last_conversation_id
        if device_context:
            payload["device_context"] = device_context

        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/agent/chat",
                json=payload,
                timeout=_TIMEOUT,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if "text" in chunk:
                            yield chunk["text"]
                        elif "tool_status" in chunk:
                            yield {"tool_status": chunk["tool_status"]}
                        elif "conversation_id" in chunk:
                            self.last_conversation_id = chunk["conversation_id"]
                        elif "error" in chunk:
                            logger.error("[GOV-CLIENT] Agent error: %s", chunk["error"])
                            yield f"[Error: {chunk['error']}]"
                    except json.JSONDecodeError:
                        yield data

        except httpx.ConnectError:
            logger.error("[GOV-CLIENT] Cannot reach governance-engine at %s", self.base_url)
            yield "[Error: Cannot reach agent server. Is governance-engine running?]"
        except httpx.TimeoutException:
            logger.error("[GOV-CLIENT] Request timed out")
            yield "[Error: Agent request timed out]"
        except Exception as exc:
            logger.error("[GOV-CLIENT] Unexpected error: %s", exc)
            yield f"[Error: {exc}]"
