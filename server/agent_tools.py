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
    # ── Confirmation Dialogue Tool ────────────────────────────────────
    {
        "name": "request_confirmation",
        "description": (
            "Show a confirmation dialogue on the device. Use for destructive or "
            "important actions that need user approval before proceeding."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Dialogue title (e.g. CONFIRM ACTION)"},
                "message": {"type": "string", "description": "What action needs confirmation"},
                "confirm_label": {"type": "string", "description": "Confirm button text", "default": "OK"},
                "cancel_label": {"type": "string", "description": "Cancel button text", "default": "CANCEL"},
                "destructive": {"type": "boolean", "description": "If true, uses red styling for confirm button", "default": False},
            },
            "required": ["title", "message"],
        },
    },
    # ── Task Management Tools ──────────────────────────────────────────
    {
        "name": "create_task",
        "description": (
            "Create a new task. The task will appear on the device, companion app, "
            "and sync to Things 3 on the laptop. Set a reminder_at to get a "
            "notification at a specific time. Priority: 1=critical, 2=high, "
            "3=normal (default), 4=low."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "What needs to be done."},
                "notes": {"type": "string", "description": "Additional context or details."},
                "due_date": {"type": "string", "description": "Due date: YYYY-MM-DD."},
                "due_time": {"type": "string", "description": "Due time: HH:MM (24h)."},
                "reminder_at": {
                    "type": "string",
                    "description": "When to send a reminder: ISO datetime YYYY-MM-DDTHH:MM:SS.",
                },
                "priority": {
                    "type": "integer",
                    "enum": [1, 2, 3, 4],
                    "description": "1=critical, 2=high, 3=normal, 4=low.",
                },
                "project": {"type": "string", "description": "Project name (default INBOX)."},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for categorization.",
                },
                "parent_id": {
                    "type": "string",
                    "description": "Parent task ID to create this as a subtask.",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_task",
        "description": (
            "Update any field(s) on an existing task. Pass only the fields "
            "you want to change."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task ID (tsk_...)."},
                "title": {"type": "string", "description": "New title."},
                "notes": {"type": "string", "description": "New notes."},
                "due_date": {"type": "string", "description": "New due date: YYYY-MM-DD."},
                "due_time": {"type": "string", "description": "New due time: HH:MM."},
                "reminder_at": {"type": "string", "description": "New reminder: ISO datetime."},
                "priority": {"type": "integer", "enum": [1, 2, 3, 4], "description": "New priority."},
                "status": {
                    "type": "string",
                    "enum": ["todo", "in_progress", "waiting", "done", "cancelled"],
                    "description": "New status.",
                },
                "project": {"type": "string", "description": "New project."},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "New tags."},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "complete_task",
        "description": (
            "Mark a task as complete/done. Sets completed_at timestamp. "
            "Use get_tasks first to find the ID if the user refers to a task by name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The task ID (tsk_...).",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "delete_task",
        "description": (
            "Delete a task. By default soft-deletes (sets status to cancelled). "
            "The task can still be found with status filter."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task ID (tsk_...)."},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "add_subtask",
        "description": (
            "Add a subtask to an existing task. Creates a new task with parent_id set."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "parent_id": {"type": "string", "description": "Parent task ID (tsk_...)."},
                "title": {"type": "string", "description": "Subtask title."},
                "priority": {"type": "integer", "enum": [1, 2, 3, 4], "description": "Priority."},
                "due_date": {"type": "string", "description": "Due date: YYYY-MM-DD."},
            },
            "required": ["parent_id", "title"],
        },
    },
    {
        "name": "get_tasks",
        "description": (
            "List tasks with flexible filtering. Returns task IDs, titles, "
            "priorities, projects, due dates, and status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["todo", "in_progress", "waiting", "done", "cancelled"],
                    "description": "Filter by status.",
                },
                "priority": {
                    "type": "integer",
                    "enum": [1, 2, 3, 4],
                    "description": "Filter by priority.",
                },
                "project": {"type": "string", "description": "Filter by project name."},
                "due_before": {"type": "string", "description": "Tasks due on or before YYYY-MM-DD."},
                "due_after": {"type": "string", "description": "Tasks due on or after YYYY-MM-DD."},
                "search": {"type": "string", "description": "Search in title and notes."},
                "limit": {"type": "integer", "description": "Max tasks to return (default 20, max 50)."},
            },
            "required": [],
        },
    },
    {
        "name": "get_task",
        "description": (
            "Get a single task by ID, including its subtasks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task ID (tsk_...)."},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "set_reminder",
        "description": (
            "Set or update the reminder time for a task. The device will receive "
            "a notification at the specified time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task ID (tsk_...)."},
                "reminder_at": {
                    "type": "string",
                    "description": "When to remind: ISO datetime YYYY-MM-DDTHH:MM:SS.",
                },
            },
            "required": ["task_id", "reminder_at"],
        },
    },
    {
        "name": "list_projects",
        "description": (
            "List all distinct project names from active tasks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
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
    {
        "name": "music_recommend",
        "description": (
            "Get music recommendations based on current track, mood, or genre. "
            "Uses Spotify's recommendation engine. Can seed from currently playing "
            "track, specific genres, or mood descriptors."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "based_on": {
                    "type": "string",
                    "enum": ["current", "mood", "genre", "artist", "history"],
                    "description": "What to base recommendations on.",
                },
                "mood": {
                    "type": "string",
                    "description": "Mood descriptor (e.g. 'chill', 'energetic', 'melancholic'). For based_on=mood.",
                },
                "genre": {
                    "type": "string",
                    "description": "Genre (e.g. 'jazz', 'electronic', 'indie'). For based_on=genre.",
                },
            },
            "required": ["based_on"],
        },
    },
    {
        "name": "music_taste_profile",
        "description": (
            "Get the user's music taste profile. Returns top artists, genres, "
            "listening patterns (time of day, day of week), and recent trends. "
            "Use this to make informed recommendations or discuss music taste."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
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

    if tool_name == "request_confirmation":
        title = tool_input.get("title", "CONFIRM")
        message = tool_input.get("message", "")
        confirm_label = tool_input.get("confirm_label", "OK")
        cancel_label = tool_input.get("cancel_label", "CANCEL")
        destructive = bool(tool_input.get("destructive", False))
        setting_changes.append({
            "key": "_confirm_dialogue",
            "value": {
                "title": title,
                "message": message,
                "confirm_label": confirm_label,
                "cancel_label": cancel_label,
                "destructive": destructive,
            },
        })
        return json.dumps({"success": True, "message": f"Confirmation dialogue shown: {title}"})

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

    if tool_name == "update_task":
        return _update_task(tool_input)

    if tool_name == "complete_task":
        return _complete_task(tool_input)

    if tool_name == "delete_task":
        return _delete_task(tool_input)

    if tool_name == "add_subtask":
        return _add_subtask(tool_input)

    if tool_name == "get_tasks":
        return _get_tasks(tool_input)

    if tool_name == "get_task":
        return _get_task_detail(tool_input)

    if tool_name == "set_reminder":
        return _set_reminder(tool_input)

    if tool_name == "list_projects":
        return _list_projects(tool_input)

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

    if tool_name == "music_recommend":
        return _music_recommend(tool_input)

    if tool_name == "music_taste_profile":
        return _music_taste_profile(tool_input)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


# ── AppleScript injection prevention ─────────────────────────────────────

import re
import subprocess


def _sanitize_applescript(value: str) -> str:
    """Sanitize a string for safe interpolation into AppleScript.

    Strips characters that could break out of a quoted string context
    or inject AppleScript commands. Only allows printable ASCII/Unicode
    text characters, spaces, and basic punctuation.
    """
    # Remove backslashes and double quotes (the escape/delimiter chars in AppleScript strings)
    value = value.replace("\\", "").replace('"', "")
    # Remove any control characters (tabs, newlines, etc.)
    value = re.sub(r"[\x00-\x1f\x7f]", "", value)
    # Limit length to prevent abuse
    value = value[:200]
    return value


# ── Integration adapter singletons ──────────────────────────────────────

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
        draft_id = gmail.create_draft("new", body, to=to, subject=subject)
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

    safe_query = _sanitize_applescript(query)
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
    calendar_name = _sanitize_applescript(tool_input.get("calendar", ""))
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


# ── Task management tool handlers (BITOS task store) ────────────────────

def _create_task(tool_input: dict) -> str:
    title = tool_input.get("title", "").strip()
    if not title:
        return json.dumps({"error": "title is required"})

    import task_store
    try:
        task = task_store.create_task(
            title=title,
            notes=tool_input.get("notes", ""),
            priority=tool_input.get("priority", 3),
            due_date=tool_input.get("due_date"),
            due_time=tool_input.get("due_time"),
            reminder_at=tool_input.get("reminder_at"),
            project=tool_input.get("project", "INBOX"),
            tags=tool_input.get("tags"),
            parent_id=tool_input.get("parent_id"),
        )
        logger.info("task_created: id=%s title=%s", task["id"], title[:40])
        return json.dumps({"success": True, "task": task})
    except Exception as exc:
        logger.warning("create_task_error: %s", exc)
        return json.dumps({"error": f"Failed to create task: {exc}"})


def _update_task(tool_input: dict) -> str:
    task_id = tool_input.get("task_id", "").strip()
    if not task_id:
        return json.dumps({"error": "task_id is required"})

    import task_store
    fields = {k: v for k, v in tool_input.items() if k != "task_id"}
    try:
        task = task_store.update_task(task_id, **fields)
        if task is None:
            return json.dumps({"error": f"Task {task_id} not found"})
        logger.info("task_updated: id=%s fields=%s", task_id, list(fields.keys()))
        return json.dumps({"success": True, "task": task})
    except Exception as exc:
        logger.warning("update_task_error: %s", exc)
        return json.dumps({"error": f"Failed to update task: {exc}"})


def _complete_task(tool_input: dict) -> str:
    task_id = tool_input.get("task_id", "")
    if not task_id:
        return json.dumps({"error": "task_id is required"})

    import task_store
    try:
        task = task_store.complete_task(str(task_id))
        if task is None:
            return json.dumps({"error": f"Task {task_id} not found"})
        logger.info("task_completed: id=%s", task_id)
        return json.dumps({"success": True, "task": task})
    except Exception as exc:
        logger.warning("complete_task_error: %s", exc)
        return json.dumps({"error": f"Failed to complete task: {exc}"})


def _delete_task(tool_input: dict) -> str:
    task_id = tool_input.get("task_id", "")
    if not task_id:
        return json.dumps({"error": "task_id is required"})

    import task_store
    try:
        ok = task_store.delete_task(task_id)
        if not ok:
            return json.dumps({"error": f"Task {task_id} not found"})
        logger.info("task_deleted: id=%s", task_id)
        return json.dumps({"success": True, "task_id": task_id, "status": "cancelled"})
    except Exception as exc:
        logger.warning("delete_task_error: %s", exc)
        return json.dumps({"error": f"Failed to delete task: {exc}"})


def _add_subtask(tool_input: dict) -> str:
    parent_id = tool_input.get("parent_id", "").strip()
    title = tool_input.get("title", "").strip()
    if not parent_id or not title:
        return json.dumps({"error": "parent_id and title are required"})

    import task_store
    try:
        # Verify parent exists
        parent = task_store.get_task(parent_id)
        if parent is None:
            return json.dumps({"error": f"Parent task {parent_id} not found"})

        task = task_store.create_task(
            title=title,
            priority=tool_input.get("priority", 3),
            due_date=tool_input.get("due_date"),
            parent_id=parent_id,
        )
        logger.info("subtask_created: id=%s parent=%s title=%s", task["id"], parent_id, title[:40])
        return json.dumps({"success": True, "subtask": task})
    except Exception as exc:
        logger.warning("add_subtask_error: %s", exc)
        return json.dumps({"error": f"Failed to add subtask: {exc}"})


def _get_tasks(tool_input: dict) -> str:
    limit = min(tool_input.get("limit", 20), 50)

    import task_store
    try:
        tasks = task_store.list_tasks(
            status=tool_input.get("status"),
            priority=tool_input.get("priority"),
            project=tool_input.get("project"),
            due_before=tool_input.get("due_before"),
            due_after=tool_input.get("due_after"),
            search=tool_input.get("search"),
            limit=limit,
        )
        return json.dumps({"tasks": tasks, "count": len(tasks)})
    except Exception as exc:
        logger.warning("get_tasks_error: %s", exc)
        return json.dumps({"error": f"Failed to get tasks: {exc}"})


def _get_task_detail(tool_input: dict) -> str:
    task_id = tool_input.get("task_id", "")
    if not task_id:
        return json.dumps({"error": "task_id is required"})

    import task_store
    try:
        task = task_store.get_task(task_id)
        if task is None:
            return json.dumps({"error": f"Task {task_id} not found"})
        return json.dumps({"task": task})
    except Exception as exc:
        logger.warning("get_task_error: %s", exc)
        return json.dumps({"error": f"Failed to get task: {exc}"})


def _set_reminder(tool_input: dict) -> str:
    task_id = tool_input.get("task_id", "")
    reminder_at = tool_input.get("reminder_at", "")
    if not task_id or not reminder_at:
        return json.dumps({"error": "task_id and reminder_at are required"})

    import task_store
    try:
        task = task_store.update_task(
            task_id,
            reminder_at=reminder_at,
            reminder_fired=0,
        )
        if task is None:
            return json.dumps({"error": f"Task {task_id} not found"})
        logger.info("reminder_set: id=%s at=%s", task_id, reminder_at)
        return json.dumps({"success": True, "task": task})
    except Exception as exc:
        logger.warning("set_reminder_error: %s", exc)
        return json.dumps({"error": f"Failed to set reminder: {exc}"})


def _list_projects(tool_input: dict) -> str:
    import task_store
    try:
        projects = task_store.list_projects()
        return json.dumps({"projects": projects, "count": len(projects)})
    except Exception as exc:
        logger.warning("list_projects_error: %s", exc)
        return json.dumps({"error": f"Failed to list projects: {exc}"})


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


# ── Mood-to-Spotify audio feature mapping ────────────────────────────────

MOOD_TO_SPOTIFY_PARAMS: dict[str, dict] = {
    "chill": {"target_energy": 0.3, "target_valence": 0.5, "target_tempo": 90},
    "energetic": {"target_energy": 0.9, "target_valence": 0.8, "target_tempo": 140},
    "melancholic": {"target_energy": 0.2, "target_valence": 0.2, "target_tempo": 80},
    "focused": {"target_energy": 0.5, "target_valence": 0.4, "target_tempo": 110,
                "target_instrumentalness": 0.8},
    "happy": {"target_energy": 0.7, "target_valence": 0.9, "target_tempo": 120},
    "angry": {"target_energy": 0.95, "target_valence": 0.3, "target_tempo": 150},
    "romantic": {"target_energy": 0.3, "target_valence": 0.6, "target_tempo": 85},
    "sleepy": {"target_energy": 0.1, "target_valence": 0.4, "target_tempo": 70},
    "workout": {"target_energy": 0.95, "target_valence": 0.7, "target_tempo": 145},
    "study": {"target_energy": 0.3, "target_valence": 0.3, "target_tempo": 100,
              "target_instrumentalness": 0.9},
    "party": {"target_energy": 0.9, "target_valence": 0.9, "target_tempo": 128,
              "target_danceability": 0.8},
}


def _music_recommend(tool_input: dict) -> str:
    sp = _get_spotify()
    if not sp.available:
        return json.dumps({"error": "Spotify not connected"})

    based_on = tool_input.get("based_on", "current")
    kwargs: dict = {}

    if based_on == "current":
        # Seed from currently playing track
        now = sp.get_now_playing()
        if not now or not now.get("uri"):
            return json.dumps({"error": "Nothing currently playing to base recommendations on"})
        track_id = now["uri"].split(":")[-1]
        recs = sp.get_recommendations(seed_tracks=[track_id], **kwargs)

    elif based_on == "mood":
        mood = tool_input.get("mood", "chill").lower()
        params = MOOD_TO_SPOTIFY_PARAMS.get(mood, MOOD_TO_SPOTIFY_PARAMS["chill"])
        # Need at least one seed — use top track or a genre seed
        now = sp.get_now_playing()
        if now and now.get("uri"):
            track_id = now["uri"].split(":")[-1]
            recs = sp.get_recommendations(seed_tracks=[track_id], **params)
        else:
            # Fall back to genre-based seeds for the mood
            genre_map = {
                "chill": ["chill"], "energetic": ["dance", "electronic"],
                "melancholic": ["sad", "acoustic"], "focused": ["ambient", "study"],
                "happy": ["happy", "pop"], "angry": ["metal", "punk"],
                "romantic": ["romance", "r-n-b"], "sleepy": ["sleep", "ambient"],
                "workout": ["work-out"], "study": ["study"], "party": ["party", "dance"],
            }
            genres = genre_map.get(mood, ["pop"])
            recs = sp.get_recommendations(seed_genres=genres, **params)

    elif based_on == "genre":
        genre = tool_input.get("genre", "pop").lower().replace(" ", "-")
        recs = sp.get_recommendations(seed_genres=[genre])

    elif based_on == "artist":
        # Search for the artist first
        query = tool_input.get("genre", tool_input.get("mood", ""))
        if query:
            results = sp.search(query, search_type="artist", limit=1)
            if results:
                artist_id = results[0]["uri"].split(":")[-1]
                recs = sp.get_recommendations(seed_artists=[artist_id])
            else:
                return json.dumps({"error": f"Artist not found: {query}"})
        else:
            return json.dumps({"error": "Specify a genre or mood field with the artist name"})

    elif based_on == "history":
        # Use top tracks as seeds
        top = sp.get_top_items(item_type="tracks", time_range="short_term", limit=5)
        if top:
            track_ids = [t["uri"].split(":")[-1] for t in top[:5]]
            recs = sp.get_recommendations(seed_tracks=track_ids)
        else:
            return json.dumps({"error": "No listening history available"})
    else:
        return json.dumps({"error": f"Unknown based_on value: {based_on}"})

    if not recs:
        return json.dumps({"recommendations": [], "count": 0, "message": "No recommendations found"})

    return json.dumps({
        "recommendations": recs[:10],
        "count": len(recs[:10]),
        "based_on": based_on,
    })


def _music_taste_profile(tool_input: dict) -> str:
    from integrations.music_logger import get_music_logger
    ml = get_music_logger()

    # Try cached profile first, rebuild if empty
    profile = ml.get_cached_profile()
    if not profile:
        profile = ml.build_taste_profile()

    if not profile:
        # Fall back to Spotify top items API
        sp = _get_spotify()
        if sp.available:
            top_artists = sp.get_top_items(item_type="artists", time_range="medium_term", limit=10)
            top_tracks = sp.get_top_items(item_type="tracks", time_range="medium_term", limit=10)
            return json.dumps({
                "source": "spotify_api",
                "top_artists": top_artists,
                "top_tracks": top_tracks,
                "note": "Taste profile based on Spotify listening history (no local history yet)",
            })
        return json.dumps({"error": "No taste profile data available"})

    return json.dumps(profile)
