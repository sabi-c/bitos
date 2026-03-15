"""Music panel — now playing + track list.

Renders into 156x280 right-panel surface.
Matches bitos-nav-v2.html .music-panel specification.
"""

import pygame

from device.ui.fonts import get_font
from device.ui.font_sizes import TITLE, BODY, CAPTION
from device.ui.panels.base import (
    BasePanel, PANEL_W, BLACK, WHITE, GRAY_555, GRAY_444,
    GRAY_1A, SEP_COLOR,
)


class MusicPanel(BasePanel):
    TITLE = "MUSIC"

    def __init__(self):
        self.now_playing = {
            "track": "NO TENDER LEFT BEHIND",
            "artist": "TENDER FEST OST",
            "position": "1:24",
            "duration": "3:42",
            "progress": 0.38,
        }
        self.tracks = [
            {"title": "NO TENDER LEFT BEHIND", "playing": True},
            {"title": "THE DIPPING POINT", "playing": False},
            {"title": "SAUCE ON MY MIND", "playing": False},
            {"title": "CRISPY DREAM", "playing": False},
        ]
        self.focused_track = 0

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)

        font_body = get_font(BODY)
        font_cap = get_font(CAPTION)
        font_ctrl = get_font(TITLE)

        # Header
        y = self.draw_header(surface, right_text="\u266a PLAYING", right_color=GRAY_555)

        # Now Playing area
        np = self.now_playing

        # Album art box (44x44, centered)
        art_size = 44
        art_x = (PANEL_W - art_size) // 2
        art_y = y + 10
        pygame.draw.rect(surface, WHITE, (art_x, art_y, art_size, art_size), 2)
        # Music note inside
        note_surf = font_ctrl.render("\u266b", False, WHITE)
        surface.blit(note_surf, (art_x + (art_size - note_surf.get_width()) // 2,
                                  art_y + (art_size - note_surf.get_height()) // 2))

        # Track name
        track_y = art_y + art_size + 4
        track_surf = font_body.render(np["track"][:18], False, WHITE)
        surface.blit(track_surf, ((PANEL_W - track_surf.get_width()) // 2, track_y))

        # Artist + time
        artist_str = f"{np['artist']} \u00b7 {np['position']}/{np['duration']}"
        artist_surf = font_cap.render(artist_str[:24], False, GRAY_444)
        artist_y = track_y + track_surf.get_height() + 2
        surface.blit(artist_surf, ((PANEL_W - artist_surf.get_width()) // 2, artist_y))

        # Progress bar
        bar_y = artist_y + artist_surf.get_height() + 6
        bar_x = 8
        bar_w = PANEL_W - 16
        bar_h = 4
        pygame.draw.rect(surface, WHITE, (bar_x, bar_y, bar_w, bar_h), 1)
        fill_w = int((bar_w - 2) * np["progress"])
        if fill_w > 0:
            pygame.draw.rect(surface, WHITE, (bar_x + 1, bar_y + 1, fill_w, bar_h - 2))

        # Playback controls (3 buttons)
        btn_y = bar_y + bar_h + 6
        btn_size = 20
        btn_gap = 4
        total_w = btn_size * 3 + btn_gap * 2
        btn_start_x = (PANEL_W - total_w) // 2
        buttons = ["\u25c0", "\u25b6", "\u25b6\u25b6"]
        for i, label in enumerate(buttons):
            bx = btn_start_x + i * (btn_size + btn_gap)
            pygame.draw.rect(surface, WHITE, (bx, btn_y, btn_size, btn_size), 2)
            btn_surf = font_ctrl.render(label, False, WHITE)
            surface.blit(btn_surf, (bx + (btn_size - btn_surf.get_width()) // 2,
                                     btn_y + (btn_size - btn_surf.get_height()) // 2))

        # Separator
        sep_y = btn_y + btn_size + 6
        pygame.draw.line(surface, WHITE, (0, sep_y), (PANEL_W, sep_y), 2)
        y = sep_y + 2

        # Track list
        track_h = 24
        for idx, track in enumerate(self.tracks):
            focused = idx == self.focused_track
            playing = track.get("playing", False)

            if focused:
                pygame.draw.rect(surface, WHITE, (0, y, PANEL_W, track_h))

            if focused:
                text_color = BLACK
            elif playing:
                text_color = WHITE
            else:
                text_color = GRAY_444

            prefix = "\u266a " if playing else ""
            label = prefix + track["title"][:16]
            label_surf = font_body.render(label, False, text_color)
            surface.blit(label_surf, (8, y + (track_h - label_surf.get_height()) // 2))

            pygame.draw.line(surface, SEP_COLOR, (0, y + track_h - 1), (PANEL_W, y + track_h - 1))
            y += track_h
