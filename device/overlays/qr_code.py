"""QR pairing/setup overlay."""
from __future__ import annotations

import pygame

from display.tokens import BLACK, DIM2, PHYSICAL_H, PHYSICAL_W, WHITE


class QROverlay:
    """
    # WHY THIS EXISTS: displays a scannable QR code on the 240×280
    # screen for companion app pairing and WiFi setup flows.
    """

    def __init__(self, url: str, title: str, subtitle: str, timeout_s: int = 120, on_connected=None, on_timeout=None, on_dismiss=None):
        self._url = url
        self._title = title
        self._subtitle = subtitle
        self._timeout_ms = timeout_s * 1000
        self._elapsed_ms = 0
        self._on_connected = on_connected
        self._on_timeout = on_timeout
        self._on_dismiss = on_dismiss
        self._qr_surface = self._make_qr_surface()

    def _make_qr_surface(self) -> pygame.Surface:
        """Generate QR matrix using qrcode and draw as pygame rects."""
        try:
            import qrcode as qr

            qrc = qr.QRCode(version=1, error_correction=qr.constants.ERROR_CORRECT_M, box_size=4, border=2)
            qrc.add_data(self._url)
            qrc.make(fit=True)
            matrix = qrc.get_matrix()
        except Exception:
            side = 29
            bits = bin(abs(hash(self._url)))[2:]
            matrix = []
            idx = 0
            for _ in range(side):
                row = []
                for _ in range(side):
                    row.append(bits[idx % len(bits)] == "1")
                    idx += 1
                matrix.append(row)
        size = len(matrix) * 4
        surf = pygame.Surface((size, size))
        surf.fill((255, 255, 255))
        for r, row in enumerate(matrix):
            for c, val in enumerate(row):
                if val:
                    pygame.draw.rect(surf, (0, 0, 0), (c * 4, r * 4, 4, 4))
        return surf

    def render(self, surface, tokens) -> None:
        surface.fill(BLACK)
        title_font = tokens.FONT_SM
        body_font = tokens.FONT_XS

        title_surface = title_font.render(self._title[:28], False, BLACK, WHITE)
        surface.blit(title_surface, (8, 8))

        qr_x = (PHYSICAL_W - self._qr_surface.get_width()) // 2
        qr_y = 40
        surface.blit(self._qr_surface, (qr_x, qr_y))

        subtitle = body_font.render(self._subtitle[:30], False, WHITE)
        surface.blit(subtitle, ((PHYSICAL_W - subtitle.get_width()) // 2, qr_y + self._qr_surface.get_height() + 12))

        remaining = max(0, (self._timeout_ms - self._elapsed_ms) // 1000)
        countdown = body_font.render(f"PAIRING MODE · {remaining}s", False, DIM2)
        surface.blit(countdown, ((PHYSICAL_W - countdown.get_width()) // 2, PHYSICAL_H - 28))

        from display.tokens import FONT_SIZES, FONT_PATH
        try:
            hint_font = pygame.font.Font(FONT_PATH, FONT_SIZES.get("hint", 4))
        except FileNotFoundError:
            hint_font = pygame.font.SysFont("monospace", 4)
        hint = hint_font.render("LONG:CANCEL", False, DIM2)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    def tick(self, dt_ms: int) -> bool:
        self._elapsed_ms += dt_ms
        if self._elapsed_ms >= self._timeout_ms:
            if self._on_timeout:
                self._on_timeout()
            return False
        return True

    def handle_input(self, event) -> bool:
        if event in {"LONG_PRESS", "DOUBLE_PRESS"} and self._on_dismiss:
            self._on_dismiss()
            return False
        return True

    def notify_connected(self) -> None:
        if self._on_connected:
            self._on_connected()
