"""Agent tool definitions and handler for BITOS device control.

Provides tools the LLM can call during chat to read/update device settings
and request user confirmation for actions.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

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
) -> str:
    """Execute an agent tool call and return the result as a string.

    Args:
        tool_name: The tool to execute.
        tool_input: Input parameters from the LLM.
        device_settings: Current device settings snapshot (from ChatRequest).
        setting_changes: Mutable list — appended with any changes to push to device.

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

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
