"""CommsPreviewPanel — unified communications (Messages + Mail).

Top area: recent message/email previews.
Below: submenu for messages, mail, contacts.
"""

from __future__ import annotations

import pygame

from device.display.theme import get_font
from device.display.tokens import WHITE, DIM2, DIM3, HAIRLINE
from device.ui.panels.base import PreviewPanel


HEADER_H = 48
HEADER_FONT = 10
PREVIEW_FONT = 9
PAD_X = 6
PAD_Y = 4
LINE_H = 14

COMMS_ITEMS = [
    {"label": "MESSAGES", "description": "View iMessages", "action": "messages"},
    {"label": "MAIL", "description": "View emails", "action": "mail"},
    {"label": "CONTACTS", "description": "Search contacts", "action": "contacts"},
    {"label": "BACK", "description": "Return to sidebar", "action": "back"},
]


class CommsPreviewPanel(PreviewPanel):
    """Preview panel for COMMS sidebar item (messages + mail unified)."""

    def __init__(self, on_action: callable):
        super().__init__(items=COMMS_ITEMS, on_action=on_action)
        self._latest_msg: str | None = None
        self._latest_mail: str | None = None
        self._msg_sender: str | None = None
        self._mail_sender: str | None = None

    def set_latest(self, msg: str | None = None, mail: str | None = None,
                   msg_sender: str | None = None, mail_sender: str | None = None) -> None:
        """Update latest message/email preview text."""
        self._latest_msg = msg
        self._latest_mail = mail
        self._msg_sender = msg_sender
        self._mail_sender = mail_sender

    def render(self, surface: pygame.Surface) -> None:
        w = surface.get_width()
        header_font = get_font(HEADER_FONT)
        preview_font = get_font(PREVIEW_FONT)

        # ── Header ──
        y = PAD_Y
        header_surf = header_font.render("COMMS", False, WHITE)
        surface.blit(header_surf, (PAD_X, y))
        y += LINE_H + 2

        # Latest previews
        has_preview = False
        if self._latest_msg:
            text = self._latest_msg[:28] + "..." if len(self._latest_msg) > 28 else self._latest_msg
            prefix = f"MSG {self._msg_sender}: " if self._msg_sender else "MSG: "
            surf = preview_font.render(f"{prefix}{text}", False, DIM2)
            surface.blit(surf, (PAD_X, y))
            y += LINE_H
            has_preview = True
        if self._latest_mail:
            text = self._latest_mail[:28] + "..." if len(self._latest_mail) > 28 else self._latest_mail
            prefix = f"MAIL {self._mail_sender}: " if self._mail_sender else "MAIL: "
            surf = preview_font.render(f"{prefix}{text}", False, DIM3)
            surface.blit(surf, (PAD_X, y))
            has_preview = True
        if not has_preview:
            surf = preview_font.render("No new messages", False, DIM3)
            surface.blit(surf, (PAD_X, y))

        # Separator
        sep_y = HEADER_H - 1
        pygame.draw.line(surface, HAIRLINE,
                         (PAD_X, sep_y), (w - PAD_X, sep_y))

        # ── Submenu items ──
        self._render_items(surface, y_offset=HEADER_H)
