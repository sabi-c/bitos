"""Maps sidebar labels to preview panels for composite screen.

Creates custom preview panels for each sidebar item wired to
action callbacks from main.py.

Sidebar items: HOME, CHAT, TASKS, ACTIVITY, COMMS, FILES, RECORD, SETTINGS, FOCUS
"""

from ui.panels.chat_preview import ChatPreviewPanel
from ui.panels.tasks_preview import TasksPreviewPanel
from ui.panels.home_preview import HomePreviewPanel
from ui.panels.activity_preview import ActivityPreviewPanel
from ui.panels.comms_preview import CommsPreviewPanel
from ui.panels.settings_preview import SettingsPreviewPanel
from ui.panels.field_recording_panel import FieldRecordingPanel
from ui.panels.generic_preview import GenericPreviewPanel


# Generic configs for items that don't have custom panels yet.
_GENERIC_CONFIGS = {
    "FILES": [
        {"label": "BROWSE", "description": "Browse files", "action": "open"},
        {"label": "RECENT", "description": "Recently opened", "action": "recent"},
        {"label": "BACK", "description": "Return to sidebar", "action": "back"},
    ],
    "FOCUS": [
        {"label": "START FOCUS", "description": "Begin focus session", "action": "open"},
        {"label": "TIMER", "description": "Set focus timer", "action": "timer"},
        {"label": "BACK", "description": "Return to sidebar", "action": "back"},
    ],
}


def create_right_panels(panel_openers: dict | None = None, repository=None,
                        status_state=None, audio_pipeline=None,
                        stt_callable=None, led=None) -> dict:
    """Create preview panels keyed by sidebar label.

    Args:
        panel_openers: dict mapping sidebar labels to opener callables.
            Used to wire submenu actions to screen transitions.
        repository: device settings repository for panels that need it.
        status_state: shared status state for settings preview header.
    """
    openers = panel_openers or {}
    panels = {}

    # ── Home: custom preview panel ──
    def home_action(action_key):
        if action_key == "back":
            return
        mapping = {"chat": "CHAT", "tasks": "TASKS", "activity": "ACTIVITY"}
        target = mapping.get(action_key)
        if target:
            opener = openers.get(target)
            if opener is not None:
                opener()

    panels["HOME"] = HomePreviewPanel(on_action=home_action)

    # ── Chat: custom preview panel ──
    def chat_action(action_key):
        if action_key == "back":
            return
        if action_key == "respond_with_text":
            # Inline recording completed — pass transcribed text to chat opener
            panel = panels.get("CHAT")
            text = panel._transcribed_text if panel else None
            opener = openers.get("CHAT_RESPOND_TEXT") or openers.get("CHAT_GREETING") or openers.get("CHAT")
            if opener is not None:
                opener(text=text)
            return
        if action_key == "respond":
            opener = openers.get("CHAT_GREETING") or openers.get("CHAT")
            if opener is not None:
                opener()
            return
        if action_key == "settings":
            opener = openers.get("CHAT_SETTINGS")
            if opener is not None:
                opener()
            return
        if action_key == "new_chat":
            opener = openers.get("CHAT_NEW") or openers.get("CHAT")
            if opener is not None:
                opener()
            return
        if action_key == "resume_chat":
            opener = openers.get("CHAT_RESUME") or openers.get("CHAT")
            if opener is not None:
                opener()
            return
        if action_key == "chat_history":
            opener = openers.get("CHAT_HISTORY")
            if opener is not None:
                opener()
            return
        opener = openers.get("CHAT")
        if opener is not None:
            opener()

    panels["CHAT"] = ChatPreviewPanel(
        on_action=chat_action,
        repository=repository,
        audio_pipeline=audio_pipeline,
        stt_callable=stt_callable,
        led=led,
    )

    # ── Tasks: custom preview panel ──
    def tasks_action(action_key):
        if action_key == "back":
            return
        opener = openers.get("TASKS")
        if opener is not None:
            opener()

    panels["TASKS"] = TasksPreviewPanel(on_action=tasks_action)

    # ── Activity: merged agent + notifications ──
    def activity_action(action_key):
        if action_key == "back":
            return
        if action_key == "notifications":
            opener = openers.get("NOTIFICATIONS") or openers.get("ACTIVITY")
            if opener is not None:
                opener()
            return
        if action_key == "agent_tasks":
            opener = openers.get("AGENT") or openers.get("ACTIVITY")
            if opener is not None:
                opener()
            return
        opener = openers.get("ACTIVITY")
        if opener is not None:
            opener()

    panels["ACTIVITY"] = ActivityPreviewPanel(on_action=activity_action)

    # ── Comms: unified messages + mail ──
    def comms_action(action_key):
        if action_key == "back":
            return
        if action_key == "messages":
            opener = openers.get("MSGS") or openers.get("COMMS")
            if opener is not None:
                opener()
            return
        if action_key == "mail":
            opener = openers.get("MAIL") or openers.get("COMMS")
            if opener is not None:
                opener()
            return
        if action_key == "contacts":
            opener = openers.get("CONTACTS")
            if opener is not None:
                opener()
            return
        opener = openers.get("COMMS")
        if opener is not None:
            opener()

    panels["COMMS"] = CommsPreviewPanel(on_action=comms_action)

    # ── Settings: device info + quick toggles ──
    def settings_action(action_key):
        if action_key == "back":
            return
        if action_key in ("toggle_voice", "toggle_mode", "toggle_volume"):
            # Quick toggles open settings directly for now
            opener = openers.get("SETTINGS")
            if opener is not None:
                opener()
            return
        opener = openers.get("SETTINGS")
        if opener is not None:
            opener()

    panels["SETTINGS"] = SettingsPreviewPanel(
        on_action=settings_action,
        status_state=status_state,
        repository=repository,
    )

    # ── Record: field recording panel ──
    def record_action(action_key):
        if action_key == "back":
            return
        if action_key == "new_recording":
            # Handled internally by the panel state machine
            return
        # view_rec_* actions could open detail view in future
        opener = openers.get("RECORD")
        if opener is not None:
            opener()

    panels["RECORD"] = FieldRecordingPanel(on_action=record_action)

    # ── Generic panels for remaining items ──
    for label, items in _GENERIC_CONFIGS.items():
        opener = openers.get(label)

        def _make_action(lbl, op):
            def action(action_key):
                if action_key == "back":
                    return
                if op is not None:
                    op()
            return action

        panels[label] = GenericPreviewPanel(
            label=label,
            items=items,
            on_action=_make_action(label, opener),
        )

    return panels
