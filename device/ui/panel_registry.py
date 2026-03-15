"""Maps sidebar labels to new render-only panel classes."""

from device.ui.panels.home import HomePanel
from device.ui.panels.chat import ChatPanel
from device.ui.panels.tasks import TasksPanel
from device.ui.panels.settings import SettingsPanel
from device.ui.panels.focus import FocusPanel
from device.ui.panels.mail import MailPanel
from device.ui.panels.messages import MessagesPanel
from device.ui.panels.music import MusicPanel
from device.ui.panels.history import HistoryPanel


def create_right_panels() -> dict:
    """Create instances of all render-only right panels, keyed by sidebar label."""
    return {
        "HOME": HomePanel(),
        "CHAT": ChatPanel(),
        "TASKS": TasksPanel(),
        "SETTINGS": SettingsPanel(),
        "FOCUS": FocusPanel(),
        "MAIL": MailPanel(),
        "MSGS": MessagesPanel(),
        "MUSIC": MusicPanel(),
        "HISTORY": HistoryPanel(),
    }
