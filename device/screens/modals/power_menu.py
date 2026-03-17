from __future__ import annotations

import pygame

from screens.base import Screen


class PowerMenuModal(Screen):
    SCREEN_NAME = "POWER"

    def handle_event(self, event):
        if self._manager:
            self._manager.dismiss_overlay()
        return True

    def get_hint(self) -> str:
        return "[tap] cancel  [hold] confirm"

    def draw(self, surface: pygame.Surface) -> None:
        shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 200))
        surface.blit(shade, (0, 0))
        pygame.draw.rect(surface, (255, 255, 255), (20, 76, 200, 88), 2)
