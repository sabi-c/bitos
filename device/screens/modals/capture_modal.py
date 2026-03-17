from __future__ import annotations

import pygame

from screens.base import Screen


class CaptureModal(Screen):
    SCREEN_NAME = "CAPTURE"

    def handle_event(self, event):
        if self._manager:
            self._manager.dismiss_overlay()
        return True

    def get_hint(self) -> str:
        return "[tap] close"

    def draw(self, surface: pygame.Surface) -> None:
        shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 200))
        surface.blit(shade, (0, 0))
        pygame.draw.rect(surface, (255, 255, 255), (30, 90, 180, 60), 2)
