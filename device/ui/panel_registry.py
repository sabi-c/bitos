"""Maps sidebar labels to minimal placeholder panels for composite screen."""
import pygame


class _PlaceholderPanel:
    """Minimal panel that renders the label name centered."""

    def __init__(self, label: str):
        self._label = label
        self._font = None

    def render(self, surface: pygame.Surface) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 12)
        w, h = surface.get_size()
        text = self._font.render(self._label, False, (80, 80, 80))
        surface.blit(text, ((w - text.get_width()) // 2, (h - text.get_height()) // 2))


_LABELS = ["HOME", "CHAT", "TASKS", "SETTINGS", "FOCUS", "MAIL", "MSGS", "MUSIC", "HISTORY"]


def create_right_panels() -> dict:
    """Create minimal placeholder panels keyed by sidebar label."""
    return {label: _PlaceholderPanel(label) for label in _LABELS}
