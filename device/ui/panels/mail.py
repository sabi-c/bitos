"""Mail panel — inbox list with sender, subject, timestamps.

Renders into 156x280 right-panel surface.
Matches bitos-nav-v2.html .mail-panel specification.
"""

import pygame

from device.ui.fonts import get_font
from device.ui.panels.base import (
    BasePanel, PANEL_W, BLACK, WHITE, GRAY_555, GRAY_333,
    GRAY_AAA, GRAY_1A, SEP_COLOR, GRAY_222,
)


class MailPanel(BasePanel):
    TITLE = "MAIL"

    def __init__(self):
        self.unread_count = 3
        self.emails = [
            {"sender": "JOAQUIN \u00b7 SSS", "subject": "RE: NIKE HOUSE INVOICE",
             "time": "9:44", "unread": True, "focused": True},
            {"sender": "OVATION TRAVEL", "subject": "LAX\u2192JFK MAR 18 ITINERARY",
             "time": "8:30", "unread": True, "focused": False},
            {"sender": "BEN WOLIN", "subject": "HYPNOTIST DOC UPDATE",
             "time": "YEST.", "unread": True, "focused": False},
            {"sender": "ANTHROPIC", "subject": "SONNET 4.6 RELEASE NOTES",
             "time": "MON", "unread": False, "focused": False},
        ]
        self.focused_email = 0

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)

        # Header with badge
        font_7 = get_font(7)
        font_5 = get_font(5)
        font_6 = get_font(6)

        # Draw header manually to include badge
        pygame.draw.rect(surface, WHITE, (0, 0, PANEL_W, 16))
        pygame.draw.line(surface, WHITE, (0, 16), (PANEL_W, 16), 2)
        title_surf = font_7.render("MAIL", False, BLACK)
        surface.blit(title_surf, (8, 5))

        # Badge
        badge_text = str(self.unread_count)
        badge_surf = font_5.render(badge_text, False, BLACK)
        bx = 8 + title_surf.get_width() + 6
        by = 5
        pygame.draw.rect(surface, BLACK, (bx - 1, by - 1,
                                          badge_surf.get_width() + 8,
                                          badge_surf.get_height() + 4), 2)
        surface.blit(badge_surf, (bx + 3, by + 1))

        y = 18

        # Email rows
        row_h = 28
        for idx, email in enumerate(self.emails):
            focused = idx == self.focused_email
            unread = email.get("unread", False)

            if focused:
                pygame.draw.rect(surface, WHITE, (0, y, PANEL_W, row_h))

            # Sender + time line
            if focused:
                from_color = BLACK
                subj_color = GRAY_555
            elif unread:
                from_color = WHITE
                subj_color = GRAY_AAA
            else:
                from_color = GRAY_AAA
                subj_color = GRAY_555

            sender_surf = font_7.render(email["sender"][:16], False, from_color)
            time_surf = font_5.render(email["time"], False, GRAY_333 if not focused else BLACK)
            surface.blit(sender_surf, (8, y + 3))
            surface.blit(time_surf, (PANEL_W - time_surf.get_width() - 8, y + 4))

            # Subject line
            subj_surf = font_6.render(email["subject"][:20], False, subj_color)
            surface.blit(subj_surf, (8, y + 3 + sender_surf.get_height() + 3))

            pygame.draw.line(surface, SEP_COLOR, (0, y + row_h - 1), (PANEL_W, y + row_h - 1))
            y += row_h

        # "OPEN FULL INBOX" footer
        pygame.draw.line(surface, GRAY_333, (0, y), (PANEL_W, y), 2)
        y += 2
        footer_surf = font_5.render("\u25b6 OPEN FULL INBOX", False, GRAY_222)
        surface.blit(footer_surf, (8, y + 6))
