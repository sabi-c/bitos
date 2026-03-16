"""Agent tool definitions and handler for BITOS device control.

Provides tools the LLM can call during chat to read/update device settings
and request user confirmation for actions.
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# ── Pending approval requests (blocking tool calls) ─────────────────────
# Maps request_id -> {"event": threading.Event, "choice": str | None}
_pending_approvals: dict[str, dict] = {}
_approvals_lock = threading.Lock()


def create_approval_request(prompt: str, options: list[str]) -> tuple[str, dict]:
    """Create a pending approval and return (request_id, sse_event_data)."""
    request_id = f"req_{uuid.uuid4().hex[:8]}"
    event = threading.Event()
    with _approvals_lock:
        _pending_approvals[request_id] = {"event": event, "choice": None}

    sse_data = {
        "approval_request": {
            "id": request_id,
            "prompt": prompt,
            "options": options[:3],
        }
    }
    return request_id, sse_data


def wait_for_approval(request_id: str, timeout: float = 60.0) -> str:
    """Block until the device responds or timeout. Returns chosen option or 'cancelled'."""
    with _approvals_lock:
        entry = _pending_approvals.get(request_id)
    if not entry:
        return "cancelled"

    entry["event"].wait(timeout=timeout)

    with _approvals_lock:
        entry = _pending_approvals.pop(request_id, {})

    return entry.get("choice") or "cancelled"


def resolve_approval(request_id: str, choice: str) -> bool:
    """Called by the /chat/approval endpoint when the device submits a choice."""
    with _approvals_lock:
        entry = _pending_approvals.get(request_id)
    if not entry:
        return False
    entry["choice"] = choice
    entry["event"].set()
    return True

# ── Tool Definitions (Anthropic tool_use format) ─────────────────────────

DEVICE_TOOLS = [
    {
        "name": "get_device_settings",
        "description": (
            "Read current device settings. Returns all settings including "
            "voice_mode, volume, tts_engine, ai_model, web_search, memory, "
            "extended_thinking, agent_mode, and any other persisted settings. "
            "Use this before suggesting or making changes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "update_device_setting",
        "description": (
            "Change a device setting. The change takes effect immediately on the device. "
            "Valid keys: volume (0-100), voice_mode (off/on/auto), tts_engine "
            "(speechify/piper/openai/espeak/auto), ai_model (default/haiku/sonnet/opus), "
            "web_search (true/false), memory (true/false), extended_thinking (true/false), "
            "agent_mode (producer/hacker/clown/monk/storyteller/director), "
            "meta_prompt (string), text_speed (slow/normal/fast)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "The setting key to change.",
                },
                "value": {
                    "description": "The new value for the setting.",
                },
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "request_approval",
        "description": (
            "Ask the user to choose between options on their device. "
            "Use this for high-impact actions that need explicit confirmation, "
            "like sending a message, making a purchase, or changing important settings. "
            "The device shows a popup with your prompt and the options. "
            "The user selects one or cancels. Max 3 options. "
            "Returns the user's choice or 'cancelled' if they dismissed it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Short question to show the user (1-2 lines).",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-3 options for the user to choose from.",
                    "maxItems": 3,
                    "minItems": 2,
                },
            },
            "required": ["prompt", "options"],
        },
    },
]


# ── Setting validation ───────────────────────────────────────────────────

SETTING_VALIDATORS: dict[str, dict[str, Any]] = {
    "volume": {"type": "int", "min": 0, "max": 100},
    "voice_mode": {"type": "choice", "choices": ["off", "on", "auto"]},
    "tts_engine": {"type": "choice", "choices": ["speechify", "piper", "openai", "espeak", "auto"]},
    "ai_model": {"type": "choice", "choices": ["default", "haiku", "sonnet", "opus", ""]},
    "web_search": {"type": "bool"},
    "memory": {"type": "bool"},
    "extended_thinking": {"type": "bool"},
    "agent_mode": {"type": "choice", "choices": ["producer", "hacker", "clown", "monk", "storyteller", "director"]},
    "meta_prompt": {"type": "str"},
    "text_speed": {"type": "choice", "choices": ["slow", "normal", "fast"]},
}


def validate_setting(key: str, value: Any) -> tuple[bool, str, Any]:
    """Validate and coerce a setting value. Returns (ok, error_msg, coerced_value)."""
    spec = SETTING_VALIDATORS.get(key)
    if not spec:
        return False, f"Unknown setting key: {key}", None

    try:
        if spec["type"] == "int":
            v = int(value)
            if v < spec.get("min", float("-inf")) or v > spec.get("max", float("inf")):
                return False, f"{key} must be between {spec['min']} and {spec['max']}", None
            return True, "", v
        if spec["type"] == "bool":
            if isinstance(value, bool):
                return True, "", value
            v = str(value).lower() in ("true", "1", "yes", "on")
            return True, "", v
        if spec["type"] == "choice":
            v = str(value).lower().strip()
            if v not in spec["choices"]:
                return False, f"{key} must be one of: {', '.join(spec['choices'])}", None
            return True, "", v
        if spec["type"] == "str":
            return True, "", str(value)
    except (ValueError, TypeError) as exc:
        return False, f"Invalid value for {key}: {exc}", None

    return False, f"Unknown type for {key}", None


# ── Tool handler ─────────────────────────────────────────────────────────

def handle_tool_call(
    tool_name: str,
    tool_input: dict,
    device_settings: dict,
    setting_changes: list[dict],
    approval_events: list[dict] | None = None,
) -> str:
    """Execute an agent tool call and return the result as a string.

    Args:
        tool_name: The tool to execute.
        tool_input: Input parameters from the LLM.
        device_settings: Current device settings snapshot (from ChatRequest).
        setting_changes: Mutable list — appended with any changes to push to device.
        approval_events: Mutable list — appended with SSE events to emit for approvals.

    Returns:
        JSON string result for the tool_result message.
    """
    if tool_name == "get_device_settings":
        return json.dumps(device_settings, indent=2)

    if tool_name == "update_device_setting":
        key = tool_input.get("key", "")
        value = tool_input.get("value")
        ok, error, coerced = validate_setting(key, value)
        if not ok:
            return json.dumps({"error": error})

        setting_changes.append({"key": key, "value": coerced})
        logger.info("agent_setting_change: %s=%s", key, coerced)
        return json.dumps({"success": True, "key": key, "value": coerced})

    if tool_name == "request_approval":
        prompt = tool_input.get("prompt", "Confirm?")
        options = tool_input.get("options", ["Yes", "No"])[:3]
        if len(options) < 2:
            options = ["Yes", "No"]

        request_id, sse_data = create_approval_request(prompt, options)
        # Queue the SSE event so the streaming generator can emit it
        if approval_events is not None:
            approval_events.append(sse_data)

        # Block until user responds (or 60s timeout)
        logger.info("approval_waiting: id=%s prompt=%s", request_id, prompt)
        choice = wait_for_approval(request_id, timeout=60.0)
        logger.info("approval_resolved: id=%s choice=%s", request_id, choice)

        return json.dumps({"choice": choice, "request_id": request_id})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
