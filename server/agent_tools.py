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
            "(speechify/chatterbox/piper/openai/espeak/auto), ai_model (default/haiku/sonnet/opus), "
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
    # ── Messaging & Communication Tools ────────────────────────────────
    {
        "name": "send_imessage",
        "description": (
            "Send an iMessage to a contact. ALWAYS use request_approval first "
            "to confirm the recipient and message content before sending. "
            "The message is sent via the server's macOS Messages app."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "Phone number or email of the recipient.",
                },
                "message": {
                    "type": "string",
                    "description": "The message text to send.",
                },
            },
            "required": ["recipient", "message"],
        },
    },
    {
        "name": "read_imessages",
        "description": (
            "Read recent iMessage conversations. Returns the latest messages "
            "from the specified contact or from all contacts if none specified."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "contact": {
                    "type": "string",
                    "description": "Phone number, email, or name to filter by. Omit for all recent.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max messages to return (default 10, max 25).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "send_email",
        "description": (
            "Create an email draft via Gmail. ALWAYS use request_approval first "
            "to confirm recipient, subject, and body. The email is saved as a "
            "draft — the user can review and send from their email client."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address.",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line.",
                },
                "body": {
                    "type": "string",
                    "description": "Email body text.",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "read_emails",
        "description": (
            "Read recent emails from the server's macOS Mail app. "
            "Returns subject, sender, date, and preview of recent messages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mailbox": {
                    "type": "string",
                    "description": "Mailbox name (default 'INBOX'). Use 'ALL' for all mailboxes.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max emails to return (default 10, max 25).",
                },
                "unread_only": {
                    "type": "boolean",
                    "description": "Only return unread emails (default false).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_contacts",
        "description": (
            "Search contacts on the server's macOS Contacts app. "
            "Returns name, phone numbers, and email addresses."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Name or partial name to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_calendar_events",
        "description": (
            "Get upcoming calendar events from the server's macOS Calendar app. "
            "Returns event title, start/end times, location, and notes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "How many days ahead to look (default 1, max 14).",
                },
                "calendar": {
                    "type": "string",
                    "description": "Specific calendar name to filter by. Omit for all calendars.",
                },
            },
            "required": [],
        },
    },
    # ── Memory Tools ─────────────────────────────────────────────────────
    {
        "name": "remember_fact",
        "description": (
            "Save a fact about the user to long-term memory. Use this when the user "
            "shares something important about themselves — preferences, personal info, "
            "projects, relationships, habits. The fact will persist across conversations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The fact to remember (e.g. 'Seb prefers dark roast coffee').",
                },
                "category": {
                    "type": "string",
                    "enum": ["preference", "personal", "work", "relationship", "habit", "health", "location", "other"],
                    "description": "Category of the fact.",
                },
            },
            "required": ["content", "category"],
        },
    },
    {
        "name": "recall_facts",
        "description": (
            "Search long-term memory for facts about the user. Use this when you need "
            "to remember something specific about the user that might have been mentioned "
            "in a previous conversation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (keywords about what you're looking for).",
                },
            },
            "required": ["query"],
        },
    },
    # ── Web Search Tool ───────────────────────────────────────────────
    {
        "name": "web_search",
        "description": (
            "Search the web for current information. Use this when the user asks about "
            "recent events, facts you're unsure about, prices, weather, news, or anything "
            "that benefits from up-to-date information. Returns titles, URLs, and snippets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query.",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 10).",
                },
            },
            "required": ["query"],
        },
    },
    # ── Task Management Tools ──────────────────────────────────────────
    {
        "name": "create_task",
        "description": (
            "Create a new task in the task manager. Returns the created task "
            "with its ID. Use this when the user wants to add a to-do, reminder, "
            "or action item."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The task title / what needs to be done.",
                },
                "description": {
                    "type": "string",
                    "description": "Optional longer description or notes for the task.",
                },
                "due_date": {
                    "type": "string",
                    "description": "Optional due date in ISO format (e.g. 2026-03-17). Omit for no due date.",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "complete_task",
        "description": (
            "Mark a task as complete/done. Requires the task ID. "
            "Use get_tasks first to find the ID if the user refers to a task by name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "The numeric ID of the task to complete.",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "get_tasks",
        "description": (
            "List tasks from the task manager. Returns task IDs, titles, "
            "projects, and done status. Use filter to narrow results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "enum": ["today", "all", "overdue"],
                    "description": "Filter: 'today' (default) for today's tasks, 'all' for everything, 'overdue' for past-due.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max tasks to return (default 20, max 50).",
                },
            },
            "required": [],
        },
    },
]

# ── Music Tools (Spotify integration) ──────────────────────────────────

MUSIC_TOOLS = [
    {
        "name": "play_music",
        "description": (
            "Play music on Spotify. Searches for the given query and plays the "
            "top result. If no query given, resumes current playback."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Song name, artist, or description to search and play. Omit to resume.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "pause_music",
        "description": "Pause the currently playing music on Spotify.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "skip_track",
        "description": "Skip to the next track on Spotify.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "previous_track",
        "description": "Go back to the previous track on Spotify.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_now_playing",
        "description": (
            "Get what's currently playing on Spotify. Returns track name, "
            "artist, album, progress, and duration."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "queue_track",
        "description": (
            "Search for a track and add it to the Spotify playback queue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Song name or artist to search and queue.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_music",
        "description": (
            "Search Spotify for tracks, artists, albums, or playlists. "
            "Returns up to 5 results with names and URIs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query.",
                },
                "type": {
                    "type": "string",
                    "enum": ["track", "artist", "album", "playlist"],
                    "description": "What to search for (default: track).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_playlists",
        "description": "List the user's Spotify playlists.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "set_music_volume",
        "description": "Set Spotify playback volume (0-100).",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "integer",
                    "description": "Volume level 0-100.",
                },
            },
            "required": ["level"],
        },
    },
]

# Combine all tools — music tools are appended to DEVICE_TOOLS
DEVICE_TOOLS = DEVICE_TOOLS + MUSIC_TOOLS


# ── Setting validation ───────────────────────────────────────────────────

SETTING_VALIDATORS: dict[str, dict[str, Any]] = {
    "volume": {"type": "int", "min": 0, "max": 100},
    "voice_mode": {"type": "choice", "choices": ["off", "on", "auto"]},
    "tts_engine": {"type": "choice", "choices": ["auto", "edge_tts", "cartesia", "speechify", "chatterbox", "piper", "openai", "espeak"]},
    "ai_model": {"type": "choice", "choices": ["default", "haiku", "sonnet", "opus", ""]},
    "web_search": {"type": "bool"},
    "memory": {"type": "bool"},
    "extended_thinking": {"type": "bool"},
    "agent_mode": {"type": "choice", "choices": ["producer", "hacker", "clown", "monk", "storyteller", "director"]},
    "meta_prompt": {"type": "str"},
    "text_speed": {"type": "choice", "choices": ["slow", "normal", "fast", "custom"]},
    "voice_id": {"type": "str"},
    "voice_params": {"type": "json"},
    "typewriter_config": {"type": "json"},
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
        if spec["type"] == "json":
            import json
            if isinstance(value, dict):
                return True, "", json.dumps(value)
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if not isinstance(parsed, dict):
                        return False, f"{key} must be a JSON object", None
                    return True, "", value
                except json.JSONDecodeError as e:
                    return False, f"{key} is not valid JSON: {e}", None
            return False, f"{key} must be a JSON object or string", None
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
    # ── Activity feed tracking ──────────────────────────────────────
    from activity_feed import track_tool_call

    def _run_tool():
        return _handle_tool_call_inner(
            tool_name, tool_input, device_settings, setting_changes, approval_events
        )

    return track_tool_call(tool_name, tool_input, _run_tool)


def _handle_tool_call_inner(
    tool_name: str,
    tool_input: dict,
    device_settings: dict,
    setting_changes: list[dict],
    approval_events: list[dict] | None = None,
) -> str:
    """Inner tool handler — actual execution logic."""
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

    # ── Messaging tools (macOS AppleScript bridge) ─────────────────────
    if tool_name == "send_imessage":
        return _send_imessage(tool_input)

    if tool_name == "read_imessages":
        return _read_imessages(tool_input)

    if tool_name == "send_email":
        return _send_email(tool_input)

    if tool_name == "read_emails":
        return _read_emails(tool_input)

    if tool_name == "get_contacts":
        return _get_contacts(tool_input)

    if tool_name == "get_calendar_events":
        return _get_calendar_events(tool_input)

    # ── Memory tools ────────────────────────────────────────────────
    if tool_name == "remember_fact":
        return _remember_fact(tool_input)

    if tool_name == "recall_facts":
        return _recall_facts(tool_input)

    # ── Web search tool ─────────────────────────────────────────────
    if tool_name == "web_search":
        from web_search import web_search_tool_handler
        return web_search_tool_handler(tool_input)

    # ── Task management tools ────────────────────────────────────────
    if tool_name == "create_task":
        return _create_task(tool_input)

    if tool_name == "complete_task":
        return _complete_task(tool_input)

    if tool_name == "get_tasks":
        return _get_tasks(tool_input)

    # ── Music tools (Spotify) ────────────────────────────────────────
    if tool_name == "play_music":
        return _play_music(tool_input)

    if tool_name == "pause_music":
        return _pause_music(tool_input)

    if tool_name == "skip_track":
        return _skip_track(tool_input)

    if tool_name == "previous_track":
        return _previous_track(tool_input)

    if tool_name == "get_now_playing":
        return _get_now_playing(tool_input)

    if tool_name == "queue_track":
        return _queue_track(tool_input)

    if tool_name == "search_music":
        return _search_music(tool_input)

    if tool_name == "get_playlists":
        return _get_playlists_tool(tool_input)

    if tool_name == "set_music_volume":
        return _set_music_volume(tool_input)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


# ── Integration adapter singletons ──────────────────────────────────────

import subprocess

_bb: object | None = None
_gmail: object | None = None
_vikunja: object | None = None
_spotify: object | None = None


def _get_bb():
    global _bb
    if _bb is None:
        from integrations.bluebubbles_adapter import BlueBubblesAdapter
        _bb = BlueBubblesAdapter()
    return _bb


def _get_gmail():
    global _gmail
    if _gmail is None:
        from integrations.gmail_adapter import GmailAdapter
        _gmail = GmailAdapter()
    return _gmail


def _get_vikunja():
    global _vikunja
    if _vikunja is None:
        from integrations.vikunja_adapter import VikunjaAdapter
        _vikunja = VikunjaAdapter()
    return _vikunja


def _get_spotify():
    global _spotify
    if _spotify is None:
        from integrations.spotify_adapter import get_spotify
        _spotify = get_spotify()
    return _spotify


# ── Messaging tool handlers ─────────────────────────────────────────────

def _send_imessage(tool_input: dict) -> str:
    recipient = tool_input.get("recipient", "")
    message = tool_input.get("message", "")
    if not recipient or not message:
        return json.dumps({"error": "recipient and message are required"})

    bb = _get_bb()
    try:
        conversations = bb.get_conversations()
        chat_id = None
        for conv in conversations:
            if recipient.lower() in conv.get("title", "").lower() or recipient in conv.get("chat_id", ""):
                chat_id = conv["chat_id"]
                break
        if not chat_id:
            chat_id = f"iMessage;+;{recipient}"

        ok = bb.send_message(chat_id, message)
        if ok:
            logger.info("imessage_sent: to=%s len=%d", recipient, len(message))
            return json.dumps({"success": True, "recipient": recipient})
        return json.dumps({"error": "Send failed"})
    except Exception as exc:
        logger.warning("imessage_send_error: %s", exc)
        return json.dumps({"error": f"Failed to send: {exc}"})


def _read_imessages(tool_input: dict) -> str:
    contact = tool_input.get("contact", "")
    limit = min(tool_input.get("limit", 10), 25)

    bb = _get_bb()
    try:
        if contact:
            conversations = bb.get_conversations()
            for conv in conversations:
                if contact.lower() in conv.get("title", "").lower() or contact in conv.get("chat_id", ""):
                    messages = bb.get_messages(conv["chat_id"], limit=limit)
                    return json.dumps({"messages": messages, "count": len(messages), "contact": conv["title"]})
            return json.dumps({"messages": [], "count": 0, "error": f"No conversation for '{contact}'"})
        else:
            conversations = bb.get_conversations(limit=limit)
            return json.dumps({"conversations": conversations, "count": len(conversations)})
    except Exception as exc:
        logger.warning("imessage_read_error: %s", exc)
        return json.dumps({"error": f"Failed to read messages: {exc}"})


def _send_email(tool_input: dict) -> str:
    to = tool_input.get("to", "")
    subject = tool_input.get("subject", "")
    body = tool_input.get("body", "")
    if not to or not subject:
        return json.dumps({"error": "to and subject are required"})

    gmail = _get_gmail()
    try:
        draft_id = gmail.create_draft("new", body)
        logger.info("email_draft: to=%s subject=%s draft=%s", to, subject, draft_id)
        return json.dumps({"success": True, "to": to, "subject": subject, "draft_id": draft_id,
                           "note": "Created as draft — send manually or approve sending"})
    except Exception as exc:
        logger.warning("email_send_error: %s", exc)
        return json.dumps({"error": f"Failed to create email: {exc}"})


def _read_emails(tool_input: dict) -> str:
    limit = min(tool_input.get("limit", 10), 25)
    unread_only = tool_input.get("unread_only", False)

    gmail = _get_gmail()
    try:
        inbox = gmail.get_inbox(limit=limit)
        if unread_only:
            inbox = [e for e in inbox if e.get("unread")]
        return json.dumps({"emails": inbox, "count": len(inbox)})
    except Exception as exc:
        logger.warning("email_read_error: %s", exc)
        return json.dumps({"error": f"Failed to read emails: {exc}"})


def _get_contacts(tool_input: dict) -> str:
    query = tool_input.get("query", "")
    if not query:
        return json.dumps({"error": "query is required"})

    safe_query = query.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
tell application "Contacts"
    set matchedPeople to (every person whose name contains "{safe_query}")
    set output to ""
    set maxCount to count of matchedPeople
    if maxCount > 10 then set maxCount to 10
    repeat with i from 1 to maxCount
        set p to item i of matchedPeople
        set pName to name of p
        set output to output & "---" & linefeed
        set output to output & "name: " & pName & linefeed
        set phoneList to value of phones of p
        set emailList to value of emails of p
        set output to output & "phones: " & (phoneList as string) & linefeed
        set output to output & "emails: " & (emailList as string) & linefeed
    end repeat
    return output
end tell
'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return json.dumps({"error": f"Contacts search failed: {result.stderr.strip()}"})

        contacts = []
        for block in result.stdout.split("---"):
            block = block.strip()
            if not block:
                continue
            contact = {}
            for line in block.split("\n"):
                if ": " in line:
                    key, val = line.split(": ", 1)
                    contact[key.strip()] = val.strip()
            if contact:
                contacts.append(contact)
        return json.dumps({"contacts": contacts, "count": len(contacts)})
    except Exception as exc:
        return json.dumps({"error": f"Contacts search failed: {exc}"})


def _get_calendar_events(tool_input: dict) -> str:
    days_ahead = min(tool_input.get("days_ahead", 1), 14)
    calendar_name = tool_input.get("calendar", "")
    cal_filter = f'of calendar "{calendar_name}"' if calendar_name else ""

    script = f'''
set now to current date
set endDate to now + ({days_ahead} * days)
tell application "Calendar"
    set output to ""
    set eventList to (every event {cal_filter} whose start date >= now and start date <= endDate)
    set maxCount to count of eventList
    if maxCount > 20 then set maxCount to 20
    repeat with i from 1 to maxCount
        set ev to item i of eventList
        set output to output & "---" & linefeed
        set output to output & "title: " & (summary of ev) & linefeed
        set output to output & "start: " & ((start date of ev) as string) & linefeed
        set output to output & "end: " & ((end date of ev) as string) & linefeed
        set evLoc to location of ev
        if evLoc is not missing value then
            set output to output & "location: " & evLoc & linefeed
        end if
        set evNotes to description of ev
        if evNotes is not missing value then
            if length of evNotes > 100 then
                set evNotes to text 1 thru 100 of evNotes
            end if
            set output to output & "notes: " & evNotes & linefeed
        end if
    end repeat
    return output
end tell
'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return json.dumps({"error": f"Calendar read failed: {result.stderr.strip()}"})

        events = []
        for block in result.stdout.split("---"):
            block = block.strip()
            if not block:
                continue
            event = {}
            for line in block.split("\n"):
                if ": " in line:
                    key, val = line.split(": ", 1)
                    event[key.strip()] = val.strip()
            if event:
                events.append(event)
        return json.dumps({"events": events, "count": len(events)})
    except Exception as exc:
        return json.dumps({"error": f"Calendar read failed: {exc}"})


# ── Memory tool handlers ──────────────────────────────────────────────────

def _remember_fact(tool_input: dict) -> str:
    content = tool_input.get("content", "").strip()
    category = tool_input.get("category", "other")
    if not content:
        return json.dumps({"error": "content is required"})

    from memory_store import add_fact
    try:
        fact_id = add_fact(content=content, source="agent", confidence=0.9, category=category)
        logger.info("agent_remember: id=%d category=%s content=%.60s", fact_id, category, content)
        return json.dumps({"success": True, "id": fact_id, "content": content})
    except Exception as exc:
        logger.warning("remember_fact_error: %s", exc)
        return json.dumps({"error": f"Failed to store fact: {exc}"})


def _recall_facts(tool_input: dict) -> str:
    query = tool_input.get("query", "").strip()
    if not query:
        return json.dumps({"error": "query is required"})

    from memory_store import search_facts
    try:
        results = search_facts(query, limit=10)
        return json.dumps({"facts": results, "count": len(results)})
    except Exception as exc:
        logger.warning("recall_facts_error: %s", exc)
        return json.dumps({"error": f"Failed to search facts: {exc}"})


# ── Task management tool handlers ────────────────────────────────────────

def _create_task(tool_input: dict) -> str:
    title = tool_input.get("title", "").strip()
    if not title:
        return json.dumps({"error": "title is required"})

    description = tool_input.get("description", "")
    # due_date passed through as metadata (Vikunja adapter handles it in body)

    vikunja = _get_vikunja()
    try:
        task = vikunja.create_task(title, details=description or None)
        if task is None:
            return json.dumps({"error": "Failed to create task"})

        logger.info("task_created: id=%s title=%s", task.get("id"), title[:40])
        return json.dumps({
            "success": True,
            "task": {
                "id": task.get("id"),
                "title": task.get("title", title),
                "mock": task.get("mock", False),
            },
        })
    except Exception as exc:
        logger.warning("create_task_error: %s", exc)
        return json.dumps({"error": f"Failed to create task: {exc}"})


def _complete_task(tool_input: dict) -> str:
    task_id = tool_input.get("task_id")
    if task_id is None:
        return json.dumps({"error": "task_id is required"})

    vikunja = _get_vikunja()
    try:
        ok = vikunja.complete_task(int(task_id))
        if ok:
            logger.info("task_completed: id=%s", task_id)
            return json.dumps({"success": True, "task_id": task_id, "status": "done"})
        return json.dumps({"error": f"Failed to complete task {task_id}"})
    except Exception as exc:
        logger.warning("complete_task_error: %s", exc)
        return json.dumps({"error": f"Failed to complete task: {exc}"})


def _get_tasks(tool_input: dict) -> str:
    task_filter = tool_input.get("filter", "today")
    limit = min(tool_input.get("limit", 20), 50)

    vikunja = _get_vikunja()
    try:
        if task_filter == "today":
            tasks = vikunja.get_today_tasks()
        elif task_filter == "all":
            tasks = vikunja.list_tasks()
        elif task_filter == "overdue":
            # Vikunja list + client-side filter for overdue
            all_tasks = vikunja.list_tasks()
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            tasks = [
                t for t in all_tasks
                if t.get("due_date") and t["due_date"] < now and not t.get("done")
            ]
        else:
            tasks = vikunja.get_today_tasks()

        tasks = tasks[:limit]
        return json.dumps({"tasks": tasks, "count": len(tasks), "filter": task_filter})
    except Exception as exc:
        logger.warning("get_tasks_error: %s", exc)
        return json.dumps({"error": f"Failed to get tasks: {exc}"})


# ── Music tool handlers (Spotify) ───────────────────────────────────────

def _play_music(tool_input: dict) -> str:
    sp = _get_spotify()
    if not sp.available:
        return json.dumps({"error": "Spotify not connected. Visit /spotify/auth to authenticate."})

    query = tool_input.get("query", "").strip()
    if not query:
        # Resume playback
        ok = sp.play()
        if ok:
            return json.dumps({"success": True, "action": "resumed"})
        return json.dumps({"error": "Failed to resume playback"})

    # Search and play top result
    results = sp.search(query, search_type="track", limit=1)
    if not results:
        return json.dumps({"error": f"No results for '{query}'"})

    track = results[0]
    ok = sp.play(uri=track["uri"])
    if ok:
        logger.info("music_play: %s by %s", track["name"], track.get("artist", ""))
        return json.dumps({
            "success": True,
            "action": "playing",
            "track": track["name"],
            "artist": track.get("artist", ""),
            "uri": track["uri"],
        })
    return json.dumps({"error": f"Failed to play '{track['name']}'"})


def _pause_music(tool_input: dict) -> str:
    sp = _get_spotify()
    if not sp.available:
        return json.dumps({"error": "Spotify not connected"})

    ok = sp.pause()
    if ok:
        return json.dumps({"success": True, "action": "paused"})
    return json.dumps({"error": "Failed to pause"})


def _skip_track(tool_input: dict) -> str:
    sp = _get_spotify()
    if not sp.available:
        return json.dumps({"error": "Spotify not connected"})

    ok = sp.skip()
    if ok:
        return json.dumps({"success": True, "action": "skipped"})
    return json.dumps({"error": "Failed to skip"})


def _previous_track(tool_input: dict) -> str:
    sp = _get_spotify()
    if not sp.available:
        return json.dumps({"error": "Spotify not connected"})

    ok = sp.previous()
    if ok:
        return json.dumps({"success": True, "action": "previous"})
    return json.dumps({"error": "Failed to go to previous track"})


def _get_now_playing(tool_input: dict) -> str:
    sp = _get_spotify()
    if not sp.available:
        return json.dumps({"error": "Spotify not connected"})

    now = sp.get_now_playing()
    if not now:
        return json.dumps({"playing": False, "message": "Nothing is currently playing"})

    progress_s = now.get("progress_ms", 0) // 1000
    duration_s = now.get("duration_ms", 0) // 1000
    return json.dumps({
        "playing": now.get("is_playing", False),
        "track": now.get("track", ""),
        "artist": now.get("artist", ""),
        "album": now.get("album", ""),
        "progress": f"{progress_s // 60}:{progress_s % 60:02d}",
        "duration": f"{duration_s // 60}:{duration_s % 60:02d}",
        "uri": now.get("uri", ""),
    })


def _queue_track(tool_input: dict) -> str:
    sp = _get_spotify()
    if not sp.available:
        return json.dumps({"error": "Spotify not connected"})

    query = tool_input.get("query", "").strip()
    if not query:
        return json.dumps({"error": "query is required"})

    results = sp.search(query, search_type="track", limit=1)
    if not results:
        return json.dumps({"error": f"No results for '{query}'"})

    track = results[0]
    ok = sp.queue_track(track["uri"])
    if ok:
        return json.dumps({
            "success": True,
            "action": "queued",
            "track": track["name"],
            "artist": track.get("artist", ""),
        })
    return json.dumps({"error": f"Failed to queue '{track['name']}'"})


def _search_music(tool_input: dict) -> str:
    sp = _get_spotify()
    if not sp.available:
        return json.dumps({"error": "Spotify not connected"})

    query = tool_input.get("query", "").strip()
    search_type = tool_input.get("type", "track")
    if not query:
        return json.dumps({"error": "query is required"})

    results = sp.search(query, search_type=search_type, limit=5)
    return json.dumps({"results": results, "count": len(results), "type": search_type})


def _get_playlists_tool(tool_input: dict) -> str:
    sp = _get_spotify()
    if not sp.available:
        return json.dumps({"error": "Spotify not connected"})

    playlists = sp.get_playlists(limit=20)
    return json.dumps({"playlists": playlists, "count": len(playlists)})


def _set_music_volume(tool_input: dict) -> str:
    sp = _get_spotify()
    if not sp.available:
        return json.dumps({"error": "Spotify not connected"})

    level = tool_input.get("level", 50)
    if not isinstance(level, int) or level < 0 or level > 100:
        return json.dumps({"error": "level must be an integer 0-100"})

    ok = sp.set_volume(level)
    if ok:
        return json.dumps({"success": True, "volume": level})
    return json.dumps({"error": f"Failed to set volume to {level}"})
