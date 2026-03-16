"""ChatPreviewPanel — ambient greeting + voice-first response field.

Top area: slow typewriter greeting from agent (3-4 lines).
First submenu item: response field (record to reply to greeting).
Below: START NEW CHAT, RESUME CHAT, CHAT HISTORY, SETTINGS, BACK TO MAIN MENU.
"""

from __future__ import annotations

import pygame

from device.display.theme import get_font
from device.display.tokens import DIM2, DIM3, HAIRLINE, WHITE
from device.display.animator import blink_cursor
from device.display.typewriter import TypewriterRenderer
from device.ui.panels.base import PreviewPanel


GREETING_H = 60
GREETING_FONT_SIZE = 8
GREETING_PAD_X = 6
GREETING_PAD_Y = 4
MAX_GREETING_CHARS = 120

CHAT_ITEMS = [
    {"label": "RECORD", "description": "Reply to greeting", "action": "respond"},
    {"label": "START NEW CHAT", "description": "Begin a new conversation", "action": "new_chat"},
    {"label": "RESUME CHAT", "description": "Continue last conversation", "action": "resume_chat", "subtext": ""},
    {"label": "CHAT HISTORY", "description": "Browse past conversations", "action": "chat_history"},
    {"label": "SETTINGS", "description": "Chat settings", "action": "settings"},
    {"label": "BACK TO MAIN MENU", "description": "Return to sidebar", "action": "back"},
]


class ChatPreviewPanel(PreviewPanel):
    """Preview panel for CHAT sidebar item."""

    def __init__(self, on_action: callable, repository=None):
        items = [dict(item) for item in CHAT_ITEMS]
        super().__init__(items=items, on_action=on_action)
        self._repository = repository
        self._greeting_text: str = ""
        self._greeting_typewriter: TypewriterRenderer | None = None
        self._greeting_revealed = False
        self._cursor_anim = blink_cursor()
        self._greeting_session_id: int | None = None

    def set_greeting(self, text: str, session_id: int | None = None) -> None:
        """Set the agent greeting text and start slow typewriter."""
        self._greeting_text = text[:MAX_GREETING_CHARS] if text else ""
        self._greeting_session_id = session_id
        if self._greeting_text and not self._greeting_revealed:
            self._greeting_typewriter = TypewriterRenderer(self._greeting_text, speed="slow")
        else:
            self._greeting_revealed = True
            self._greeting_typewriter = None

    def set_resume_info(self, title: str, time_ago: str) -> None:
        """Update RESUME CHAT item with last chat info."""
        for item in self.items:
            if item["action"] == "resume_chat":
                item["subtext"] = f"{title} \u00b7 {time_ago}"
                break

    def update(self, dt: float) -> None:
        self._cursor_anim.update(dt)
        if self._greeting_typewriter and not self._greeting_typewriter.finished:
            self._greeting_typewriter.update(dt)
        elif self._greeting_typewriter and self._greeting_typewriter.finished:
            self._greeting_revealed = True
            self._greeting_typewriter = None

    def render(self, surface: pygame.Surface) -> None:
        font = get_font(GREETING_FONT_SIZE)
        w = surface.get_width()

        # Greeting banner (top area)
        if self._greeting_text:
            if self._greeting_typewriter:
                visible = self._greeting_typewriter.get_visible_text()
            else:
                visible = self._greeting_text

            lines = _wrap_text(visible, font, w - GREETING_PAD_X * 2)
            y = GREETING_PAD_Y
            line_h = font.get_height() + 2
            for line in lines:
                if y + line_h > GREETING_H - 4:
                    break
                surf = font.render(line, False, DIM3)
                surface.blit(surf, (GREETING_PAD_X, y))
                y += line_h

            # Blinking cursor while typing
            if self._greeting_typewriter and not self._greeting_typewriter.finished:
                # StepAnimator.step: 0 = on, 1 = off
                cursor_char = "_" if self._cursor_anim.step == 0 else " "
                cursor_surf = font.render(cursor_char, False, DIM2)
                if lines:
                    last_line_w = font.size(lines[-1])[0]
                    cy = GREETING_PAD_Y + (len(lines) - 1) * line_h
                    surface.blit(cursor_surf, (GREETING_PAD_X + last_line_w, cy))

        # Separator
        pygame.draw.line(surface, HAIRLINE,
                         (GREETING_PAD_X, GREETING_H - 1),
                         (w - GREETING_PAD_X, GREETING_H - 1))

        # Submenu items below greeting
        self._render_items(surface, y_offset=GREETING_H)


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
