"""ActionBar component — bottom gesture hints with icons.

Replaces the old HintBar. Shows gesture icons + labels, 20px tall.
Each screen/mode sets actions as (icon_type, label) tuples.
Icon types: 'tap' (circle outline), 'double' (double circle), 'hold' (filled circle).
"""

import pygame

from display.tokens import DIM2, DIM3, HAIRLINE, PHYSICAL_W

ACTION_BAR_H = 20
PAD_Y = 4

DEFAULT_ACTIONS = [
    ("tap", "NEXT"),
    ("double", "SELECT"),
    ("hold", "BACK"),
]


class ActionBar:
    """Renders the bottom action bar with gesture icons."""

    def __init__(self):
        self.actions: list[tuple[str, str]] = list(DEFAULT_ACTIONS)
        self.text: str = ""

    def set_actions(self, actions: list[tuple[str, str]]) -> None:
        """Set action items. icon_type: 'tap', 'double', or 'hold'."""
        self.actions = list(actions)
        self.text = ""

    def set_text(self, text: str) -> None:
        """Set plain text mode (no icons)."""
        self.text = text
        self.actions = []

    def render(self, surface: pygame.Surface, y: int, width: int = PHYSICAL_W) -> None:
        """Draw action bar at y position across full width."""
        from display.theme import load_ui_font

        font = load_ui_font("small", {})

        # Top separator
        pygame.draw.line(surface, HAIRLINE, (0, y), (width, y))

        center_y = y + ACTION_BAR_H // 2

        # Plain text mode
        if self.text:
            text_surf = font.render(self.text, False, DIM3)
            surface.blit(text_surf, ((width - text_surf.get_width()) // 2, center_y - text_surf.get_height() // 2))
            return

        if not self.actions:
            return

        # Render items with icons, evenly spaced
        items = []
        for icon_type, label in self.actions:
            label_surf = font.render(label, False, DIM2)
            items.append((icon_type, label_surf))

        total_width = sum(8 + 4 + s.get_width() for _, s in items)
        spacing = (width - total_width) // (len(items) + 1)
        x = spacing

        for icon_type, label_surf in items:
            icon_center = (x + 4, center_y)
            if icon_type == "tap":
                pygame.draw.circle(surface, DIM2, icon_center, 3, 1)
            elif icon_type == "double":
                pygame.draw.circle(surface, DIM2, icon_center, 3, 1)
                pygame.draw.circle(surface, DIM2, icon_center, 1, 1)
            elif icon_type == "hold":
                pygame.draw.circle(surface, DIM2, icon_center, 3, 0)

            surface.blit(label_surf, (x + 8 + 4, center_y - label_surf.get_height() // 2))
            x += 8 + 4 + label_surf.get_width() + spacing
