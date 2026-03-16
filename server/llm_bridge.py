"""Provider-agnostic LLM bridge implementations for BITOS chat streaming."""
from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)


@dataclass
class LLMBridge:
    """Base bridge contract for pluggable model providers."""

    provider: str
    model: str

    def stream_text(self, message: str, system_prompt: str | None = None, model_override: str | None = None, extended_thinking: bool = False) -> Generator[str, None, None]:
        raise NotImplementedError

    def complete_text(self, prompt: str, system_prompt: str | None = None, model_override: str | None = None) -> tuple[str, int, int]:
        """Non-streaming completion. Returns (response_text, input_tokens, output_tokens)."""
        text = "".join(self.stream_text(prompt, system_prompt=system_prompt, model_override=model_override))
        return text, 0, 0


class AnthropicBridge(LLMBridge):
    def __init__(self, api_key: str, model: str):
        super().__init__(provider="anthropic", model=model)
        self._api_key = api_key

    def stream_text(self, message: str, system_prompt: str | None = None, model_override: str | None = None, extended_thinking: bool = False) -> Generator[str, None, None]:
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        active_model = model_override or self.model
        client = anthropic.Anthropic(api_key=self._api_key)

        kwargs: dict = {
            "model": active_model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": message}],
            "system": system_prompt or SYSTEM_PROMPT,
        }

        # Extended thinking requires higher max_tokens and a thinking budget
        if extended_thinking:
            kwargs["max_tokens"] = 16000
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": 10000}

        try:
            with client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield text
        except anthropic.AuthenticationError as exc:
            logger.error("anthropic_auth_error: %s", exc)
            raise RuntimeError("Invalid API key") from exc
        except anthropic.RateLimitError as exc:
            logger.warning("anthropic_rate_limit: %s", exc)
            raise RuntimeError("Rate limited — try again in a moment") from exc
        except anthropic.APIStatusError as exc:
            logger.error("anthropic_api_error: status=%s error=%s", exc.status_code, exc)
            raise RuntimeError(f"Anthropic API error ({exc.status_code})") from exc
        except anthropic.APIConnectionError as exc:
            logger.error("anthropic_connection_error: %s", exc)
            raise RuntimeError("Cannot reach Anthropic API") from exc

    def stream_with_tools(
        self,
        message: str,
        tools: list[dict],
        tool_handler,
        device_settings: dict,
        system_prompt: str | None = None,
        model_override: str | None = None,
        extended_thinking: bool = False,
    ) -> Generator[str | dict, None, list[dict]]:
        """Stream with tool_use support. Yields text chunks or SSE event dicts, returns setting changes.

        When the model calls a tool, we resolve it and continue the conversation.
        Max 5 tool rounds to prevent infinite loops.
        Yields dicts for special SSE events (approval_request) that the caller must emit.
        """
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        from agent_tools import handle_tool_call, create_approval_request, wait_for_approval

        active_model = model_override or self.model
        client = anthropic.Anthropic(api_key=self._api_key)
        setting_changes: list[dict] = []

        messages = [{"role": "user", "content": message}]
        sys = system_prompt or SYSTEM_PROMPT

        try:
            for _round in range(5):
                kwargs: dict = {
                    "model": active_model,
                    "max_tokens": 1024,
                    "messages": messages,
                    "system": sys,
                    "tools": tools,
                }
                if extended_thinking:
                    kwargs["max_tokens"] = 16000
                    kwargs["thinking"] = {"type": "enabled", "budget_tokens": 10000}

                logger.info("tool_round=%d model=%s", _round, active_model)
                response = client.messages.create(**kwargs)

                # Process response blocks
                has_tool_use = False
                tool_results = []
                assistant_content = []

                for block in response.content:
                    assistant_content.append(block)
                    if block.type == "text":
                        yield block.text
                    elif block.type == "tool_use":
                        has_tool_use = True
                        logger.info("tool_call: name=%s input=%s", block.name, json.dumps(block.input)[:200])

                        if block.name == "request_approval":
                            # Special handling: yield SSE event BEFORE blocking
                            prompt = block.input.get("prompt", "Confirm?")
                            options = block.input.get("options", ["Yes", "No"])[:3]
                            if len(options) < 2:
                                options = ["Yes", "No"]
                            request_id, sse_data = create_approval_request(prompt, options)
                            # Yield the SSE event dict — caller will emit it
                            yield sse_data
                            # Now block until device responds
                            choice = wait_for_approval(request_id, timeout=60.0)
                            result = json.dumps({"choice": choice, "request_id": request_id})
                        else:
                            result = handle_tool_call(
                                block.name, block.input, device_settings, setting_changes,
                            )

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                if not has_tool_use:
                    return setting_changes

                # Continue conversation with tool results
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

            logger.warning("tool_loop_exhausted: hit 5-round limit")
            return setting_changes
        except anthropic.AuthenticationError as exc:
            logger.error("anthropic_auth_error_tools: %s", exc)
            raise RuntimeError("Invalid API key") from exc
        except anthropic.RateLimitError as exc:
            logger.warning("anthropic_rate_limit_tools: %s", exc)
            raise RuntimeError("Rate limited — try again in a moment") from exc
        except anthropic.APIStatusError as exc:
            logger.error("anthropic_api_error_tools: status=%s error=%s", exc.status_code, exc)
            raise RuntimeError(f"Anthropic API error ({exc.status_code})") from exc

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
