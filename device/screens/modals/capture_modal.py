from __future__ import annotations

import pygame

from device.screens.base import Screen
from device.screens.nav import NavigationEvent


class CaptureModal(Screen):
    SCREEN_NAME = "CAPTURE"

    def handle_nav(self, event: str) -> bool:
        if event in (NavigationEvent.BACK, NavigationEvent.SELECT, NavigationEvent.NEXT):
            if self._manager:
                self._manager.dismiss_overlay()
            return True
        return True

    def get_hint(self) -> str:
        return "[tap] close"

    def draw(self, surface: pygame.Surface) -> None:
        shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 200))
        surface.blit(shade, (0, 0))
        pygame.draw.rect(surface, (255, 255, 255), (30, 90, 180, 60), 2)
        surface.blit(pygame.font.SysFont("monospace", 12).render("CAPTURE", False, (255, 255, 255)), (78, 114))
