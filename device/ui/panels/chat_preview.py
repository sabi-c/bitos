"""ChatPreviewPanel — preview panel for the CHAT sidebar item.

Top area shows last assistant message (dimmed) or a prompt.
Bottom area has submenu items for chat actions.
"""

from __future__ import annotations

import pygame

from device.display.theme import get_font
from device.display.tokens import DIM2, DIM3, HAIRLINE
from device.ui.panels.base import PreviewPanel


PREVIEW_H = 80  # Top preview area height
PREVIEW_FONT_SIZE = 8
PREVIEW_PAD_X = 6
PREVIEW_PAD_Y = 4
MAX_PREVIEW_CHARS = 200

CHAT_ITEMS = [
    {"label": "START NEW CHAT", "description": "Begin a new conversation", "action": "new_chat"},
    {"label": "RESUME CHAT", "description": "Continue last conversation", "action": "resume_chat"},
    {"label": "CHAT HISTORY", "description": "Browse past conversations", "action": "chat_history"},
    {"label": "SETTINGS", "description": "Chat settings", "action": "settings"},
    {"label": "BACK", "description": "Return to sidebar", "action": "back"},
]


class ChatPreviewPanel(PreviewPanel):
    """Preview panel for CHAT sidebar item."""

    def __init__(self, on_action: callable, repository=None):
        super().__init__(items=CHAT_ITEMS, on_action=on_action)
        self._repository = repository
        self._last_message: str | None = None

    def _get_preview_text(self) -> str:
        """Get last assistant message or default prompt."""
        if self._last_message is not None:
            return self._last_message
        # No repository-level chat history method yet — show prompt
        return "Hold to start talking"

    def set_last_message(self, text: str | None) -> None:
        """Update the preview text from outside (e.g., after a chat ends)."""
        self._last_message = text

    def render(self, surface: pygame.Surface) -> None:
        font = get_font(PREVIEW_FONT_SIZE)
        w = surface.get_width()

        # ── Top preview area ──
        text = self._get_preview_text()
        if len(text) > MAX_PREVIEW_CHARS:
            text = text[:MAX_PREVIEW_CHARS - 3] + "..."

        # Word-wrap into preview area
        lines = _wrap_text(text, font, w - PREVIEW_PAD_X * 2)
        y = PREVIEW_PAD_Y
        line_h = font.get_height() + 2
        for line in lines:
            if y + line_h > PREVIEW_H - 4:
                # Render ellipsis on last visible line
                surf = font.render(line[:20] + "...", False, DIM3)
                surface.blit(surf, (PREVIEW_PAD_X, y))
                break
            surf = font.render(line, False, DIM3)
            surface.blit(surf, (PREVIEW_PAD_X, y))
            y += line_h

        # Separator line between preview and menu
        pygame.draw.line(surface, HAIRLINE,
                         (PREVIEW_PAD_X, PREVIEW_H - 1),
                         (w - PREVIEW_PAD_X, PREVIEW_H - 1))

        # ── Submenu items below preview ──
        self._render_items(surface, y_offset=PREVIEW_H)


def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Simple word-wrap."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if font.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]
