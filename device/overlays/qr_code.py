"""QR pairing/setup overlay."""
from __future__ import annotations

import pygame

from display.tokens import BLACK, DIM2, PHYSICAL_H, PHYSICAL_W, WHITE, FONT_PATH, FONT_SIZES, STATUS_BAR_H


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
        self._fonts: dict[str, pygame.font.Font] = {}
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
        title_font = self._font("small")
        body_font = self._font("body")
        hint_font = self._font("hint")

        # ── Status bar: inverted, 18px ──
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title_surface = title_font.render(self._title[:28], False, BLACK)
        surface.blit(title_surface, (6, (STATUS_BAR_H - title_surface.get_height()) // 2))

        qr_x = (PHYSICAL_W - self._qr_surface.get_width()) // 2
        qr_y = STATUS_BAR_H + 16
        surface.blit(self._qr_surface, (qr_x, qr_y))

        subtitle = body_font.render(self._subtitle[:30], False, WHITE)
        surface.blit(subtitle, ((PHYSICAL_W - subtitle.get_width()) // 2, qr_y + self._qr_surface.get_height() + 12))

        remaining = max(0, (self._timeout_ms - self._elapsed_ms) // 1000)
        countdown = body_font.render(f"PAIRING MODE \u00b7 {remaining}s", False, DIM2)
        surface.blit(countdown, ((PHYSICAL_W - countdown.get_width()) // 2, PHYSICAL_H - 28))

        hint = hint_font.render("LONG:CANCEL", False, DIM2)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    def _font(self, key: str) -> pygame.font.Font:
        if key in self._fonts:
            return self._fonts[key]
        try:
            font = pygame.font.Font(FONT_PATH, FONT_SIZES[key])
        except FileNotFoundError:
            font = pygame.font.SysFont("monospace", FONT_SIZES[key])
        self._fonts[key] = font
        return font

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
