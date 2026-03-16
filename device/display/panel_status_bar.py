"""Shared status bar renderer for list-style panels."""
import pygame
from display.tokens import BLACK, WHITE, PHYSICAL_W, STATUS_BAR_H


def render_panel_status_bar(
    surface: pygame.Surface,
    title: str,
    font: pygame.font.Font,
    right_text: str = "",
    bg_color=WHITE,
    text_color=BLACK,
) -> None:
    """Render a status bar with title (left) and optional right text."""
    pygame.draw.rect(surface, bg_color, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
    title_surf = font.render(title, False, text_color)
    surface.blit(title_surf, (6, (STATUS_BAR_H - title_surf.get_height()) // 2))
    if right_text:
        right_surf = font.render(right_text, False, text_color)
        surface.blit(right_surf, (PHYSICAL_W - right_surf.get_width() - 6,
                                   (STATUS_BAR_H - right_surf.get_height()) // 2))
