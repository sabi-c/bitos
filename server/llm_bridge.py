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

    def stream_text(self, message: str, system_prompt: str | None = None, model_override: str | None = None) -> Generator[str, None, None]:
        raise NotImplementedError

    def complete_text(self, prompt: str, system_prompt: str | None = None, model_override: str | None = None) -> tuple[str, int, int]:
        """Non-streaming completion. Returns (response_text, input_tokens, output_tokens)."""
        text = "".join(self.stream_text(prompt, system_prompt=system_prompt, model_override=model_override))
        return text, 0, 0


class AnthropicBridge(LLMBridge):
    def __init__(self, api_key: str, model: str):
        super().__init__(provider="anthropic", model=model)
        self._api_key = api_key

    def stream_text(self, message: str, system_prompt: str | None = None, model_override: str | None = None) -> Generator[str, None, None]:
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        active_model = model_override or self.model
        client = anthropic.Anthropic(api_key=self._api_key)
        with client.messages.stream(
            model=active_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": message}],
            system=system_prompt or SYSTEM_PROMPT,
        ) as stream:
            for text in stream.text_stream:
                yield text

    def complete_text(self, prompt: str, system_prompt: str | None = None, model_override: str | None = None) -> tuple[str, int, int]:
        """Non-streaming completion. Returns (response_text, input_tokens, output_tokens)."""
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        active_model = model_override or self.model
        client = anthropic.Anthropic(api_key=self._api_key)
        response = client.messages.create(
            model=active_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            system=system_prompt or SYSTEM_PROMPT,
        )
        text = "".join(block.text for block in response.content if hasattr(block, "text"))
        return text, response.usage.input_tokens, response.usage.output_tokens


class OpenAICompatibleBridge(LLMBridge):
    """Works with OpenAI-compatible `/v1/chat/completions` endpoints.

    Supports any local server (OpenClaw, NanoClaw, llama.cpp, Ollama, etc.)
    that exposes the OpenAI chat completions API.  Accepts ``ws://`` and
    ``wss://`` URLs (transparently converted to ``http``/``https`` for
    the REST call).  API key is optional — omit or leave empty for local
    servers that don't require auth.
    """

    def __init__(self, provider: str, api_key: str, base_url: str, model: str):
        super().__init__(provider=provider, model=model)
        self._api_key = api_key
        self._base_url = _normalise_base_url(base_url)

    def stream_text(self, message: str, system_prompt: str | None = None, model_override: str | None = None) -> Generator[str, None, None]:
        url = f"{self._base_url}/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        active_model = model_override or self.model
        body = {
            "model": active_model,
            "messages": [
                {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            "temperature": 0.2,
            "stream": True,
        }

        # Try SSE streaming first; fall back to non-streaming on error.
        try:
            yield from self._stream_sse(url, headers, body)
        except Exception:
            body["stream"] = False
            yield from self._request_sync(url, headers, body)

    # -- internal -----------------------------------------------------------

    def _stream_sse(self, url: str, headers: dict, body: dict) -> Generator[str, None, None]:
        with httpx.stream("POST", url, headers=headers, json=body, timeout=45.0) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload.strip() == "[DONE]":
                    break
                chunk = json.loads(payload)
                delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                text = delta.get("content")
                if text:
                    yield text

    def _request_sync(self, url: str, headers: dict, body: dict) -> Generator[str, None, None]:
        response = httpx.post(url, headers=headers, json=body, timeout=45.0)
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

    def stream_text(self, message: str, system_prompt: str | None = None, model_override: str | None = None) -> Generator[str, None, None]:
        _ = system_prompt, model_override
        out = f"[echo] {message.strip()}"
        for token in out.split(" "):
            if token:
                yield token + " "


def _normalise_base_url(url: str) -> str:
    """Convert ws(s):// to http(s):// and ensure path ends with /v1."""
    url = url.strip().rstrip("/")
    if url.startswith("ws://"):
        url = "http://" + url[len("ws://"):]
    elif url.startswith("wss://"):
        url = "https://" + url[len("wss://"):]
    # Ensure the URL ends with a /v1 path so /chat/completions resolves correctly.
    if not url.endswith("/v1"):
        url += "/v1"
    return url


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
