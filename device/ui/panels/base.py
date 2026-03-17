"""PreviewPanel — base class for sidebar preview panels with submenu navigation."""

from __future__ import annotations

import pygame

from display.theme import get_font
from display.tokens import WHITE, BLACK, DIM2, DIM3, DIM4, HAIRLINE


ITEM_H = 22
FONT_SIZE = 11
PAD_X = 6
PAD_Y = 3
INDICATOR = "> "
EMPTY_STATE_FONT_SIZE = 9


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

            # Determine item height first (needed for highlight)
            item_h = ITEM_H
            subtext = item.get("subtext")
            if subtext:
                item_h = ITEM_H + subtext_font.get_height() + 2

            if selected:
                # Highlight background: subtle dark fill + left accent bar
                highlight_color = (20, 20, 20)
                pygame.draw.rect(surface, highlight_color,
                                 (0, y, w, item_h))
                # Left accent bar (2px white)
                pygame.draw.rect(surface, WHITE, (0, y + 2, 2, item_h - 4))
                text = INDICATOR + label
                color = WHITE
            else:
                text = "  " + label
                color = DIM3

            text_surf = font.render(text, False, color)
            surface.blit(text_surf, (PAD_X, y + PAD_Y))

            # Render subtext if present
            if subtext:
                sub_color = DIM2 if selected else DIM3
                sub_surf = subtext_font.render("  " + subtext, False, sub_color)
                surface.blit(sub_surf, (PAD_X, y + PAD_Y + font.get_height() + 1))

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

    def _render_empty_state(self, surface: pygame.Surface, message: str,
                            y_offset: int = 0) -> None:
        """Render a centered empty-state message in dim text.

        Useful when a panel has no data to display (e.g. 'No tasks yet').
        """
        font = get_font(EMPTY_STATE_FONT_SIZE)
        w = surface.get_width()
        h = surface.get_height()
        text_surf = font.render(message, False, DIM4)
        tx = (w - text_surf.get_width()) // 2
        ty = y_offset + (h - y_offset) // 3
        surface.blit(text_surf, (tx, ty))

    def _render_loading(self, surface: pygame.Surface, y_offset: int = 0,
                         label: str = "LOADING") -> None:
        """Render an animated loading indicator (dots cycling 0-3)."""
        import time
        font = get_font(FONT_SIZE)
        dot_count = int(time.time() * 3) % 4
        dots = "." * dot_count
        text_surf = font.render(label + dots, False, DIM3)
        surface.blit(text_surf, (PAD_X, y_offset + PAD_Y))

    def update(self, dt: float) -> None:
        """Optional animation hook."""
        pass
