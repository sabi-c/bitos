"""BITOS Lock screen with 4-digit PIN entry (single-button)."""
import time
import logging
import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM3, HAIRLINE, PHYSICAL_W, PHYSICAL_H, STATUS_BAR_H
from display.theme import merge_runtime_ui_settings, load_ui_font
from power.battery import BatteryMonitor

_RED = (255, 0, 0)
_DEFAULT_PIN = "1234"


class LockScreen(BaseScreen):
    """PIN-gated lock screen with single-button digit cycling."""

    _owns_status_bar: bool = True

    def __init__(self, on_home=None, ui_settings: dict | None = None, repository=None):
        self._on_home = on_home
        self._is_unlocking = False
        self._repository = repository
        self._ui_settings = merge_runtime_ui_settings(ui_settings)

        self._font_clock = load_ui_font("time_large", self._ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)
        self._clock_text = ""
        self._date_text = ""
        self._last_clock_update = 0.0

        # PIN state
        self._pin = self._load_pin()
        self._entered: list[int] = []       # confirmed digits
        self._current_digit: int = 0        # cycling digit (0-9)
        self._cycling: bool = False         # True after first SHORT_PRESS on a new position

        # Error flash state
        self._flash_until: float = 0.0      # time.time() when flash ends
        self._flash_color = _RED

        # Bypass overlay state
        self._bypass_message: str | None = None
        self._bypass_until: float = 0.0


        logging.getLogger(__name__).info(
            "lock_screen pin_len=%d", len(self._pin),
        )

    def _load_pin(self) -> str:
        if self._repository:
            val = self._repository.get_setting("device_pin", default=_DEFAULT_PIN)
            if val and isinstance(val, str) and len(val) >= 4:
                return val
        return _DEFAULT_PIN

    def update(self, dt: float):
        now = time.time()
        if now - self._last_clock_update >= 1.0:
            t = time.localtime()
            self._clock_text = f"{t.tm_hour:02d}:{t.tm_min:02d}"
            days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
            months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                      "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
            self._date_text = f"{days[t.tm_wday]} {months[t.tm_mon - 1]} {t.tm_mday}"
            self._last_clock_update = now

    def handle_action(self, action: str):
        # Ignore input during error flash
        if time.time() < self._flash_until:
            return

        if action == "SHORT_PRESS":
            self._cycling = True
            self._current_digit = (self._current_digit + 1) % 10
        elif action == "DOUBLE_PRESS":
            self._entered.append(self._current_digit)
            self._current_digit = 0
            self._cycling = False
            if len(self._entered) == 4:
                self._verify_pin()
        elif action == "LONG_PRESS":
            if self._entered:
                self._entered.pop()
                self._current_digit = 0
                self._cycling = False

    def handle_input(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            return
        # Desktop keyboard shortcuts for testing
        if event.key == pygame.K_SPACE:
            self.handle_action("SHORT_PRESS")
        elif event.key == pygame.K_RETURN:
            self.handle_action("DOUBLE_PRESS")
        elif event.key == pygame.K_BACKSPACE:
            self.handle_action("LONG_PRESS")

    def render(self, surface: pygame.Surface):
        is_flashing = time.time() < self._flash_until
        bg = _RED if is_flashing else BLACK

        surface.fill(bg)

        # ── Status bar ──
        bar_bg = WHITE if not is_flashing else _RED
        bar_fg = BLACK if not is_flashing else WHITE
        pygame.draw.rect(surface, bar_bg, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("BITOS", False, bar_fg)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        # Status bar clock (right-aligned)
        if self._clock_text:
            bar_clock = self._font_small.render(self._clock_text, False, bar_fg)
            surface.blit(bar_clock, (PHYSICAL_W - bar_clock.get_width() - 6,
                                     (STATUS_BAR_H - bar_clock.get_height()) // 2))

        text_color = WHITE

        # ── Large clock ──
        clock_surf = self._font_clock.render(self._clock_text or "00:00", False, text_color)
        clock_x = (PHYSICAL_W - clock_surf.get_width()) // 2
        clock_y = STATUS_BAR_H + 20
        surface.blit(clock_surf, (clock_x, clock_y))

        # ── Date ──
        date_surf = self._font_small.render(self._date_text or "", False, DIM3 if not is_flashing else text_color)
        date_x = (PHYSICAL_W - date_surf.get_width()) // 2
        date_y = clock_y + clock_surf.get_height() + 6
        surface.blit(date_surf, (date_x, date_y))

        # ── PIN display ──
        pin_y = date_y + date_surf.get_height() + 24
        self._draw_pin_dots(surface, pin_y, text_color, is_flashing)

        # ── Separator line ──
        sep_y = pin_y + 24
        line_color = HAIRLINE if not is_flashing else text_color
        pygame.draw.line(surface, line_color, (40, sep_y), (PHYSICAL_W - 40, sep_y))

        # ── Hint text ──
        hint1 = self._font_hint.render("SHORT:NEXT \u00b7 DBL:ENTER", False, DIM3 if not is_flashing else text_color)
        hint1_x = (PHYSICAL_W - hint1.get_width()) // 2
        hint1_y = sep_y + 8
        surface.blit(hint1, (hint1_x, hint1_y))

        hint2 = self._font_hint.render("LONG:DELETE", False, DIM3 if not is_flashing else text_color)
        hint2_x = (PHYSICAL_W - hint2.get_width()) // 2
        hint2_y = hint1_y + hint1.get_height() + 4
        surface.blit(hint2, (hint2_x, hint2_y))

        # ── Bypass overlay ──
        if self._bypass_message and time.time() < self._bypass_until:
            overlay = pygame.Surface((PHYSICAL_W, 32))
            overlay.fill(WHITE)
            msg = self._font_body.render(self._bypass_message, False, BLACK)
            overlay.blit(msg, ((PHYSICAL_W - msg.get_width()) // 2,
                               (32 - msg.get_height()) // 2))
            surface.blit(overlay, (0, PHYSICAL_H // 2 - 16))
            return  # skip battery during bypass flash

        # ── Battery ──
        try:
            batt = BatteryMonitor().get_status()
            pct = batt.get("pct", 0)
            charging = batt.get("charging", False)
            icon = "\u26a1" if charging else ""
            batt_text = f"{icon} {pct}%" if icon else f"{pct}%"
            batt_color = DIM3 if (pct > 20 and not is_flashing) else text_color
            batt_surf = self._font_small.render(batt_text, False, batt_color)
            batt_x = (PHYSICAL_W - batt_surf.get_width()) // 2
            batt_y = PHYSICAL_H - batt_surf.get_height() - 6
            surface.blit(batt_surf, (batt_x, batt_y))
        except Exception:
            pass

    def _draw_pin_dots(self, surface: pygame.Surface, y: int, color, is_flashing: bool):
        """Draw confirmed dots + current cycling digit with inverted highlight."""
        spacing = 10  # pixels between digit slots

        # Build list of (text, is_active) tuples
        parts: list[tuple[str, bool]] = []
        for _d in self._entered:
            parts.append(("\u25cf", False))  # filled circle — confirmed

        if len(self._entered) < 4:
            if self._cycling:
                parts.append((str(self._current_digit), True))  # active digit
            else:
                parts.append(("_", True))  # waiting for first press

        # Pad remaining slots
        remaining = 4 - len(self._entered) - (1 if len(self._entered) < 4 else 0)
        for _ in range(remaining):
            parts.append(("_", False))

        # Pre-render to measure total width
        rendered: list[tuple[pygame.Surface, bool, int, int]] = []
        total_w = 0
        for text, active in parts:
            if active:
                # Same font size, inverted colors for emphasis
                surf = self._font_body.render(text, False, BLACK if not is_flashing else WHITE)
            else:
                surf = self._font_body.render(text, False, color)
            rendered.append((surf, active, surf.get_width(), surf.get_height()))
            total_w += surf.get_width() + spacing
        total_w -= spacing  # remove trailing space

        # Draw centered
        dx = (PHYSICAL_W - total_w) // 2
        for surf, active, w, h in rendered:
            if active:
                # Inverted background highlight + underline
                pad_x, pad_y = 3, 2
                bg_rect = pygame.Rect(dx - pad_x, y - pad_y, w + pad_x * 2, h + pad_y * 2)
                bg_color = WHITE if not is_flashing else color
                pygame.draw.rect(surface, bg_color, bg_rect)
                surface.blit(surf, (dx, y))
                # Underline beneath the box
                pygame.draw.line(
                    surface, bg_color,
                    (bg_rect.left, bg_rect.bottom + 1),
                    (bg_rect.right - 1, bg_rect.bottom + 1),
                )
            else:
                surface.blit(surf, (dx, y))
            dx += w + spacing

    def _verify_pin(self):
        entered_str = "".join(str(d) for d in self._entered)
        if entered_str == self._pin:
            self._unlock()
        else:
            # Wrong PIN: flash red and reset
            self._flash_until = time.time() + 0.3
            self._entered.clear()
            self._current_digit = 0
            self._cycling = False

    def bypass_unlock(self):
        """5-press bypass: show brief overlay then unlock."""
        if self._is_unlocking:
            return
        self._bypass_message = "BYPASS PASSCODE"
        self._bypass_until = time.time() + 0.6
        # Delayed unlock after overlay shows
        import threading
        threading.Timer(0.6, self._unlock).start()

    def _unlock(self):
        if self._is_unlocking:
            return
        self._is_unlocking = True
        if self._on_home:
            self._on_home()
