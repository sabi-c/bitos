"""Maps sidebar labels to preview panels for composite screen.

Creates ChatPreviewPanel, TasksPreviewPanel, and GenericPreviewPanel
instances wired to action callbacks from main.py.
"""

from device.ui.panels.chat_preview import ChatPreviewPanel
from device.ui.panels.tasks_preview import TasksPreviewPanel
from device.ui.panels.generic_preview import GenericPreviewPanel


# Default submenu items for generic panels.
# Each item needs: label, description, action key.
_GENERIC_CONFIGS = {
    "HOME": [
        {"label": "OVERVIEW", "description": "Home overview", "action": "open"},
        {"label": "BACK", "description": "Return to sidebar", "action": "back"},
    ],
    "SETTINGS": [
        {"label": "OPEN SETTINGS", "description": "Full settings panel", "action": "open"},
        {"label": "BACK", "description": "Return to sidebar", "action": "back"},
    ],
    "FOCUS": [
        {"label": "START FOCUS", "description": "Begin focus session", "action": "open"},
        {"label": "BACK", "description": "Return to sidebar", "action": "back"},
    ],
    "MAIL": [
        {"label": "VIEW MAIL", "description": "Open mail panel", "action": "open"},
        {"label": "BACK", "description": "Return to sidebar", "action": "back"},
    ],
    "MSGS": [
        {"label": "VIEW MESSAGES", "description": "Open messages panel", "action": "open"},
        {"label": "BACK", "description": "Return to sidebar", "action": "back"},
    ],
    "MUSIC": [
        {"label": "NOW PLAYING", "description": "Music controls", "action": "open"},
        {"label": "BACK", "description": "Return to sidebar", "action": "back"},
    ],
    "HISTORY": [
        {"label": "VIEW HISTORY", "description": "Browse captures", "action": "open"},
        {"label": "BACK", "description": "Return to sidebar", "action": "back"},
    ],
}


def create_right_panels(panel_openers: dict | None = None) -> dict:
    """Create preview panels keyed by sidebar label.

    Args:
        panel_openers: dict mapping sidebar labels to opener callables.
            Used to wire submenu actions to screen transitions.
    """
    openers = panel_openers or {}
    panels = {}

    # ── Chat: custom preview panel ──
    def chat_action(action_key):
        if action_key == "back":
            return  # handled by CompositeScreen (returns focus to sidebar)
        opener = openers.get("CHAT")
        if opener is not None:
            opener()

    panels["CHAT"] = ChatPreviewPanel(on_action=chat_action)

    # ── Tasks: custom preview panel ──
    def tasks_action(action_key):
        if action_key == "back":
            return  # handled by CompositeScreen
        opener = openers.get("TASKS")
        if opener is not None:
            opener()

    panels["TASKS"] = TasksPreviewPanel(on_action=tasks_action)

    # ── Generic panels for remaining items ──
    for label, items in _GENERIC_CONFIGS.items():
        opener = openers.get(label)

        def _make_action(lbl, op):
            def action(action_key):
                if action_key == "back":
                    return  # handled by CompositeScreen
                if action_key == "open" and op is not None:
                    op()
            return action

        panels[label] = GenericPreviewPanel(
            label=label,
            items=items,
            on_action=_make_action(label, opener),
        )

    return panels
