"""PreviewPanel — base class for sidebar preview panels with submenu navigation."""

from __future__ import annotations

import pygame

from device.display.theme import get_font
from device.display.tokens import WHITE, BLACK, DIM2, DIM3, HAIRLINE


ITEM_H = 20
FONT_SIZE = 10
PAD_X = 6
PAD_Y = 3
INDICATOR = "> "


class PreviewPanel:
    """Base for custom sidebar preview panels with submenu navigation.

    Each panel has a list of submenu items and routes SHORT/DOUBLE presses.
    DOUBLE executes the selected item's action via the on_action callback.
    """

    def __init__(self, items: list[dict], on_action: callable):
        """
        Args:
            items: list of {"label": str, "description": str, "action": str}
            on_action: callback(action_key) when an item is executed
        """
        self.items = items
        self.selected_index = -1  # No highlight until submenu is entered
        self._on_action = on_action

    def handle_action(self, action: str) -> bool:
        """Handle button action. Returns True if consumed."""
        if action == "SHORT_PRESS":
            self.selected_index = (self.selected_index + 1) % len(self.items)
            return True
        elif action == "DOUBLE_PRESS":
            if self.selected_index < 0:
                return False  # Not focused yet
            item = self.items[self.selected_index]
            self._on_action(item["action"])
            return True
        return False

    def render(self, surface: pygame.Surface) -> None:
        """Render submenu items. Override in subclasses for custom top areas."""
        self._render_items(surface, y_offset=0)

    def _render_items(self, surface: pygame.Surface, y_offset: int = 0) -> None:
        """Render the submenu item list starting at y_offset."""
        font = get_font(FONT_SIZE)
        w = surface.get_width()

        for idx, item in enumerate(self.items):
            y = y_offset + idx * ITEM_H
            if y + ITEM_H > surface.get_height():
                break

            selected = idx == self.selected_index
            label = item["label"]

            if selected:
                text = INDICATOR + label
                color = WHITE
            else:
                text = "  " + label
                color = DIM3

            text_surf = font.render(text, False, color)
            surface.blit(text_surf, (PAD_X, y + PAD_Y))

            # Subtle separator
            if not selected and y + ITEM_H - 1 < surface.get_height():
                pygame.draw.line(surface, HAIRLINE,
                                 (PAD_X, y + ITEM_H - 1),
                                 (w - PAD_X, y + ITEM_H - 1))

    def update(self, dt: float) -> None:
        """Optional animation hook."""
        pass
