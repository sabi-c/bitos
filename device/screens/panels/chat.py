"""
BITOS Chat Panel (Phase 1 — simplified)
Text input via keyboard, streaming response rendered line-by-line.
"""
import threading
import pygame

from screens.base import BaseScreen
from display.tokens import (
    BLACK, WHITE, DIM2, DIM3, HAIRLINE,
    PHYSICAL_W, PHYSICAL_H, FONT_PATH, FONT_SIZES, PAD_ROW
)
from display.animator import blink_cursor
from client.api import BackendClient


class ChatPanel(BaseScreen):
    """Simplified chat: keyboard input → streaming Claude response."""

    def __init__(self, client: BackendClient):
        self._client = client
        self._cursor_anim = blink_cursor()

        # State
        self._input_text = ""
        self._messages: list[dict] = []  # {"role": "user"|"assistant", "text": "..."}
        self._is_streaming = False
        self._scroll_offset = 0

        # Font
        try:
            self._font = pygame.font.Font(FONT_PATH, FONT_SIZES["body"])
            self._font_small = pygame.font.Font(FONT_PATH, FONT_SIZES["small"])
        except FileNotFoundError:
            self._font = pygame.font.SysFont("monospace", FONT_SIZES["body"])
            self._font_small = pygame.font.SysFont("monospace", FONT_SIZES["small"])

        self._line_height = self._font.get_height() + PAD_ROW

    def update(self, dt: float):
        self._cursor_anim.update(dt)

    def handle_input(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            return

        if self._is_streaming:
            return  # Ignore input while streaming

        if event.key == pygame.K_RETURN:
            self._send_message()
        elif event.key == pygame.K_BACKSPACE:
            self._input_text = self._input_text[:-1]
        elif event.key == pygame.K_UP:
            self._scroll_offset = max(0, self._scroll_offset - 1)
        elif event.key == pygame.K_DOWN:
            self._scroll_offset += 1
        elif event.unicode and event.unicode.isprintable():
            self._input_text += event.unicode

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # ── Header ──
        header_y = 2
        header_text = self._font_small.render("CHAT", False, DIM3)
        surface.blit(header_text, (4, header_y))
        pygame.draw.line(surface, HAIRLINE, (0, header_y + 10), (PHYSICAL_W, header_y + 10))

        # ── Messages area ──
        msg_y = header_y + 14
        max_y = PHYSICAL_H - 24  # Leave room for input bar

        visible_lines = []
        for msg in self._messages:
            prefix = "> " if msg["role"] == "user" else ""
            color = DIM2 if msg["role"] == "user" else WHITE
            lines = self._wrap_text(prefix + msg["text"], PHYSICAL_W - 8)
            for line in lines:
                visible_lines.append((line, color))

        # Apply scroll
        start = max(0, len(visible_lines) - int((max_y - msg_y) / self._line_height) - self._scroll_offset)
        for line_text, color in visible_lines[start:]:
            if msg_y > max_y:
                break
            text_surface = self._font.render(line_text, False, color)
            surface.blit(text_surface, (4, msg_y))
            msg_y += self._line_height

        # ── Streaming indicator ──
        if self._is_streaming:
            dots = "." * ((pygame.time.get_ticks() // 400) % 4)
            indicator = self._font_small.render(dots, False, DIM3)
            surface.blit(indicator, (4, max_y - 8))

        # ── Input bar ──
        input_y = PHYSICAL_H - 18
        pygame.draw.line(surface, HAIRLINE, (0, input_y - 4), (PHYSICAL_W, input_y - 4))

        display_text = self._input_text
        if len(display_text) > 28:
            display_text = "..." + display_text[-25:]

        input_surface = self._font.render(display_text, False, WHITE)
        surface.blit(input_surface, (4, input_y))

        # Cursor
        if not self._is_streaming and self._cursor_anim.step == 0:
            cursor_x = 4 + input_surface.get_width() + 1
            pygame.draw.rect(surface, WHITE, (cursor_x, input_y, 6, self._font.get_height()))

    def _send_message(self):
        text = self._input_text.strip()
        if not text:
            return

        self._messages.append({"role": "user", "text": text})
        self._input_text = ""
        self._is_streaming = True
        self._scroll_offset = 0

        # Stream response in background thread
        thread = threading.Thread(target=self._stream_response, args=(text,), daemon=True)
        thread.start()

    def _stream_response(self, message: str):
        try:
            response_text = ""
            self._messages.append({"role": "assistant", "text": ""})

            for chunk in self._client.chat(message):
                response_text += chunk
                self._messages[-1]["text"] = response_text
        except Exception as e:
            self._messages.append({"role": "assistant", "text": f"[error: {e}]"})
        finally:
            self._is_streaming = False

    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        """Simple character-level word wrap."""
        lines = []
        current = ""
        for char in text:
            if char == "\n":
                lines.append(current)
                current = ""
                continue
            test = current + char
            w = self._font.size(test)[0]
            if w <= max_width:
                current = test
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
        return lines or [""]
