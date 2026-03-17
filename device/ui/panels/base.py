"""PreviewPanel — base class for sidebar preview panels with submenu navigation."""

from __future__ import annotations

import pygame

from device.display.theme import get_font
from device.display.tokens import WHITE, BLACK, DIM2, DIM3, HAIRLINE


ITEM_H = 22
FONT_SIZE = 11
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
        self._scroll_offset = 0  # Index of first visible item

    def handle_action(self, action: str) -> bool:
        """Handle button action. Returns True if consumed."""
        if not self.items:
            return False
        if action == "SHORT_PRESS":
            self.selected_index = (self.selected_index + 1) % len(self.items)
            # Wrap scroll offset when selection wraps to top
            if self.selected_index == 0:
                self._scroll_offset = 0
            return True
        elif action == "DOUBLE_PRESS":
            if self.selected_index < 0 or self.selected_index >= len(self.items):
                return False  # Not focused yet or out of bounds
            item = self.items[self.selected_index]
            self._on_action(item["action"])
            return True
        return False

    def render(self, surface: pygame.Surface) -> None:
        """Render submenu items. Override in subclasses for custom top areas."""
        self._render_items(surface, y_offset=0)

    def _render_items(self, surface: pygame.Surface, y_offset: int = 0) -> None:
        """Render the submenu item list starting at y_offset, with scroll support."""
        font = get_font(FONT_SIZE)
        w = surface.get_width()
        available_h = surface.get_height() - y_offset
        max_visible = max(1, available_h // ITEM_H)

        # Auto-scroll: ensure selected item is visible
        if self.selected_index >= 0:
            if self.selected_index >= self._scroll_offset + max_visible:
                self._scroll_offset = self.selected_index - max_visible + 1
            elif self.selected_index < self._scroll_offset:
                self._scroll_offset = self.selected_index

        # Clamp scroll offset
        max_scroll = max(0, len(self.items) - max_visible)
        self._scroll_offset = max(0, min(self._scroll_offset, max_scroll))

        # Render visible items
        subtext_font = get_font(FONT_SIZE - 2)
        visible_items = self.items[self._scroll_offset:self._scroll_offset + max_visible]
        y = y_offset
        for vi, item in enumerate(visible_items):
            idx = self._scroll_offset + vi

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

            item_h = ITEM_H
            # Render subtext if present
            subtext = item.get("subtext")
            if subtext:
                sub_surf = subtext_font.render("  " + subtext, False, DIM3)
                surface.blit(sub_surf, (PAD_X, y + PAD_Y + font.get_height() + 1))
                item_h = ITEM_H + subtext_font.get_height() + 2

            # Subtle separator
            if not selected and y + item_h - 1 < surface.get_height():
                pygame.draw.line(surface, HAIRLINE,
                                 (PAD_X, y + item_h - 1),
                                 (w - PAD_X, y + item_h - 1))

            y += item_h

        # Show scroll indicator if more items below
        if self._scroll_offset + max_visible < len(self.items):
            indicator_y = y_offset + max_visible * ITEM_H - ITEM_H // 2
            ind_surf = font.render("▼", False, DIM2)
            surface.blit(ind_surf, (w - PAD_X - ind_surf.get_width(), indicator_y))

    def update(self, dt: float) -> None:
        """Optional animation hook."""
        pass
