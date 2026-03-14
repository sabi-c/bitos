"""Provider-agnostic LLM bridge implementations for BITOS chat streaming."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Generator

import anthropic
import httpx

from config import (
    ANTHROPIC_API_KEY,
    MODEL_NAME,
    LLM_PROVIDER,
    SYSTEM_PROMPT,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    OPENCLAW_API_KEY,
    OPENCLAW_BASE_URL,
    OPENCLAW_MODEL,
    NANOCLAW_API_KEY,
    NANOCLAW_BASE_URL,
    NANOCLAW_MODEL,
)


@dataclass
class LLMBridge:
    """Base bridge contract for pluggable model providers."""

    provider: str
    model: str

    def stream_text(self, message: str, system_prompt: str | None = None) -> Generator[str, None, None]:
        raise NotImplementedError


class AnthropicBridge(LLMBridge):
    def __init__(self, api_key: str, model: str):
        super().__init__(provider="anthropic", model=model)
        self._api_key = api_key

    def stream_text(self, message: str, system_prompt: str | None = None) -> Generator[str, None, None]:
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        client = anthropic.Anthropic(api_key=self._api_key)
        with client.messages.stream(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": message}],
            system=system_prompt or SYSTEM_PROMPT,
        ) as stream:
            for text in stream.text_stream:
                yield text


class OpenAICompatibleBridge(LLMBridge):
    """Works with OpenAI-compatible `/v1/chat/completions` endpoints."""

    def __init__(self, provider: str, api_key: str, base_url: str, model: str):
        super().__init__(provider=provider, model=model)
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def stream_text(self, message: str, system_prompt: str | None = None) -> Generator[str, None, None]:
        if not self._api_key:
            raise RuntimeError(f"{self.provider.upper()} API key not configured")

        response = httpx.post(
            f"{self._base_url}/chat/completions",
            timeout=45.0,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
                    {"role": "user", "content": message},
                ],
                "temperature": 0.2,
            },
        )
        response.raise_for_status()
        payload = response.json()

        text = _extract_openai_content(payload)
        if not text:
            raise RuntimeError(f"{self.provider} returned no text content")

        chunk_size = 120
        for i in range(0, len(text), chunk_size):
            yield text[i : i + chunk_size]


class EchoBridge(LLMBridge):
    """Deterministic fallback bridge for local testing."""

    def __init__(self):
        super().__init__(provider="echo", model="echo-v1")

    def stream_text(self, message: str, system_prompt: str | None = None) -> Generator[str, None, None]:
        _ = system_prompt
        out = f"[echo] {message.strip()}"
        for token in out.split(" "):
            if token:
                yield token + " "


def _extract_openai_content(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""

    msg = choices[0].get("message") or {}
    content = msg.get("content", "")
    if isinstance(content, str):
        return content

    # Some compatible providers return structured parts.
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "".join(parts)

    return ""


def create_llm_bridge() -> LLMBridge:
    provider = (LLM_PROVIDER or "anthropic").lower()

    if provider == "anthropic":
        return AnthropicBridge(api_key=ANTHROPIC_API_KEY, model=MODEL_NAME)
    if provider == "openai":
        return OpenAICompatibleBridge(
            provider="openai",
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            model=OPENAI_MODEL,
        )
    if provider == "openclaw":
        return OpenAICompatibleBridge(
            provider="openclaw",
            api_key=OPENCLAW_API_KEY,
            base_url=OPENCLAW_BASE_URL,
            model=OPENCLAW_MODEL,
        )
    if provider == "nanoclaw":
        return OpenAICompatibleBridge(
            provider="nanoclaw",
            api_key=NANOCLAW_API_KEY,
            base_url=NANOCLAW_BASE_URL,
            model=NANOCLAW_MODEL,
        )
    if provider == "echo":
        return EchoBridge()

    raise RuntimeError(
        f"Unsupported LLM_PROVIDER='{provider}'. Expected one of: anthropic, openai, openclaw, nanoclaw, echo"
    )


def to_sse_data(text: str) -> str:
    return f"data: {json.dumps({'text': text})}\n\n"
