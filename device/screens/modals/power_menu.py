from __future__ import annotations

import pygame

from device.screens.base import Screen
from device.screens.nav import NavigationEvent


class PowerMenuModal(Screen):
    SCREEN_NAME = "POWER"

    def handle_nav(self, event: str) -> bool:
        if event in (NavigationEvent.BACK, NavigationEvent.NEXT):
            if self._manager:
                self._manager.dismiss_overlay()
            return True
        if event == NavigationEvent.SELECT:
            if self._manager:
                self._manager.dismiss_overlay()
            return True
        return True

    def get_hint(self) -> str:
        return "[tap] cancel  [hold] confirm"

    def draw(self, surface: pygame.Surface) -> None:
        shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 200))
        surface.blit(shade, (0, 0))
        pygame.draw.rect(surface, (255, 255, 255), (20, 76, 200, 88), 2)
        surface.blit(pygame.font.SysFont("monospace", 12).render("POWER", False, (255, 255, 255)), (90, 114))
