"""Antigravity Bridge: HTTP client for the AG Phone Chat CDP bridge.

Talks to AG Phone Chat's /api/* endpoints to drive Antigravity remotely.
Used by the voice handler to inject transcribed speech and capture responses.
"""
import logging
from typing import Optional

import httpx

log = logging.getLogger(__name__)


class AGBridge:
    """Client for AG Phone Chat's CDP bridge API."""

    def __init__(
        self,
        base_url: str = "http://localhost:3000",
        timeout_ms: int = 120_000,
        poll_ms: int = 500,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_ms = timeout_ms
        self.poll_ms = poll_ms

    # ── Core API Calls ──────────────────────────────────────────────

    async def inject_and_wait(
        self,
        text: str,
        timeout_ms: Optional[int] = None,
    ) -> dict:
        """Send text to Antigravity and wait for the complete response.

        Returns:
            {ok: True, text: "...", durationMs: int}  on success
            {ok: False, error: "...", ...}             on failure
        """
        payload = {
            "text": text,
            "timeoutMs": timeout_ms or self.timeout_ms,
            "pollMs": self.poll_ms,
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout((timeout_ms or self.timeout_ms) / 1000 + 10)
        ) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/api/inject-and-wait",
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                log.error("AG Bridge HTTP error: %s", e)
                return {"ok": False, "error": f"http_{e.response.status_code}"}
            except httpx.ConnectError:
                log.error("AG Bridge connection refused at %s", self.base_url)
                return {"ok": False, "error": "connection_refused"}
            except Exception as e:
                log.error("AG Bridge unexpected error: %s", e)
                return {"ok": False, "error": str(e)}

    async def inject(self, text: str) -> dict:
        """Fire-and-forget message injection (no wait for response)."""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/api/inject",
                    json={"text": text},
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                log.error("AG Bridge inject error: %s", e)
                return {"ok": False, "error": str(e)}

    async def get_state(self) -> dict:
        """Get current Antigravity app state (mode, model, isGenerating)."""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(f"{self.base_url}/api/state")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                log.error("AG Bridge state error: %s", e)
                return {"error": str(e)}

    async def get_snapshot(self, fresh: bool = False) -> dict:
        """Capture current chat state."""
        params = {"fresh": "true"} if fresh else {}
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/api/snapshot",
                    params=params,
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                log.error("AG Bridge snapshot error: %s", e)
                return {"error": str(e)}

    async def new_chat(self) -> dict:
        """Start a new chat in Antigravity."""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.post(f"{self.base_url}/api/new-chat")
                resp.raise_for_status()
                # Also clear conversation history for the new chat
                await self.clear_history()
                return resp.json()
            except Exception as e:
                log.error("AG Bridge new_chat error: %s", e)
                return {"error": str(e)}

    async def get_history(self) -> dict:
        """Get full accumulated conversation history."""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(f"{self.base_url}/api/history")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                log.error("AG Bridge history error: %s", e)
                return {"messages": [], "error": str(e)}

    async def clear_history(self) -> dict:
        """Clear conversation history (for new chat sessions)."""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.post(f"{self.base_url}/api/history/clear")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                log.error("AG Bridge clear_history error: %s", e)
                return {"error": str(e)}

    async def health_check(self) -> bool:
        """Check if AG Phone Chat server is reachable."""
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
            except Exception:
                return False
