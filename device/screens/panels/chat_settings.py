"""ChatSettingsPanel — voice-configurable chat settings."""

from __future__ import annotations

import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM1, DIM2, DIM3, HAIRLINE, PHYSICAL_W, PHYSICAL_H, SAFE_INSET, STATUS_BAR_H
from display.theme import load_ui_font, merge_runtime_ui_settings, ui_line_height


class ChatSettingsPanel(BaseScreen):
    """Full-screen chat settings with voice-driven editing."""

    _owns_status_bar = True

    def __init__(self, repository, on_back, ui_settings=None):
        self._repository = repository
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._line_height = ui_line_height(self._font, self._ui_settings)
        self._selected = 0

        # Load current values
        meta = self._repository.get_setting("meta_prompt", "default assistant")
        text_speed = self._repository.get_setting("text_speed", "normal")
        voice_speed = self._repository.get_setting("voice_speed", "normal")

        self._settings = [
            {"label": "META PROMPT", "key": "meta_prompt", "value": str(meta or "default assistant")},
            {"label": "TEXT SPEED", "key": "text_speed", "value": str(text_speed or "normal")},
            {"label": "VOICE SPEED", "key": "voice_speed", "value": str(voice_speed or "normal")},
        ]

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._selected = (self._selected + 1) % len(self._settings)
        elif action == "TRIPLE_PRESS":
            self._selected = (self._selected - 1) % len(self._settings)
        elif action == "LONG_PRESS":
            if self._on_back:
                self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # Status bar
        header = self._font_small.render("CHAT SETTINGS", False, WHITE)
        surface.blit(header, (SAFE_INSET, SAFE_INSET + (STATUS_BAR_H - header.get_height()) // 2))
        pygame.draw.line(surface, HAIRLINE, (0, SAFE_INSET + STATUS_BAR_H - 1), (PHYSICAL_W, SAFE_INSET + STATUS_BAR_H - 1))

        # Settings list
        y = SAFE_INSET + STATUS_BAR_H + 8
        for idx, setting in enumerate(self._settings):
            selected = idx == self._selected
            label_color = WHITE if selected else DIM3
            value_color = DIM2

            prefix = "> " if selected else "  "
            label_surf = self._font.render(prefix + setting["label"], False, label_color)
            surface.blit(label_surf, (SAFE_INSET, y))
            y += self._line_height

            # Truncated value
            val_text = setting["value"]
            if len(val_text) > 28:
                val_text = val_text[:25] + "..."
            val_surf = self._font_small.render(f'  "{val_text}"', False, value_color)
            surface.blit(val_surf, (SAFE_INSET, y))
            y += self._line_height + 4

        # Hint bar
        hint_y = PHYSICAL_H - SAFE_INSET - 20
        pygame.draw.line(surface, HAIRLINE, (0, hint_y), (PHYSICAL_W, hint_y))
        hint = self._font_small.render("tap: select \u00b7 hold: speak to edit", False, DIM1)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, hint_y + 4))

    def update(self, dt: float):
        pass
