"""ChatSettingsPanel — voice-configurable chat settings."""

from __future__ import annotations

import logging
import os

import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM1, DIM2, DIM3, HAIRLINE, PHYSICAL_W, PHYSICAL_H, SAFE_INSET, STATUS_BAR_H
from display.theme import load_ui_font, merge_runtime_ui_settings, ui_line_height

logger = logging.getLogger(__name__)

# TTS engines available on the device (detected at runtime)
_TTS_ENGINES = ["auto", "edge_tts", "speechify", "chatterbox", "piper", "openai", "espeak"]


class ChatSettingsPanel(BaseScreen):
    """Full-screen chat settings with voice-driven editing."""

    _owns_status_bar = True

    def __init__(self, repository, on_back, ui_settings=None):
        self._repository = repository
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._line_height = ui_line_height(self._font, self._ui_settings)
        self._selected = 0
        self._scroll_offset = 0  # For scrolling when list exceeds screen

        # Load current values
        voice_mode = self._repository.get_setting("voice_mode", "auto")
        volume = self._repository.get_setting("volume", 100)
        tts_engine = self._repository.get_setting("tts_engine", "auto")
        meta = self._repository.get_setting("meta_prompt", "default assistant")
        text_speed = self._repository.get_setting("text_speed", "normal")
        web_search = self._repository.get_setting("web_search", True)
        memory = self._repository.get_setting("memory", True)
        extended_thinking = self._repository.get_setting("extended_thinking", False)
        ai_model = self._repository.get_setting("ai_model", "")

        self._settings = [
            {"label": "VOICE MODE", "key": "voice_mode", "value": str(voice_mode or "auto"),
             "options": ["off", "on", "auto"]},
            {"label": "VOLUME", "key": "volume", "value": str(int(volume if volume is not None else 100)),
             "options": [str(v) for v in range(0, 110, 10)]},
            {"label": "TTS ENGINE", "key": "tts_engine", "value": str(tts_engine or "auto"),
             "options": _TTS_ENGINES},
            {"label": "TEST VOICE", "key": "_test_voice", "value": "tap to test", "action": True},
            {"label": "WEB SEARCH", "key": "web_search",
             "value": "on" if _to_bool(web_search) else "off",
             "options": ["on", "off"]},
            {"label": "MEMORY", "key": "memory",
             "value": "on" if _to_bool(memory) else "off",
             "options": ["on", "off"]},
            {"label": "THINKING", "key": "extended_thinking",
             "value": "on" if _to_bool(extended_thinking) else "off",
             "options": ["on", "off"]},
            {"label": "AI MODEL", "key": "ai_model", "value": str(ai_model or "default"),
             "options": ["default", "haiku", "sonnet", "opus"]},
            {"label": "META PROMPT", "key": "meta_prompt", "value": str(meta or "default assistant")},
            {"label": "TEXT SPEED", "key": "text_speed", "value": str(text_speed or "normal"),
             "options": ["slow", "normal", "fast", "custom"]},
        ]
        self._test_voice_status = ""

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._selected = (self._selected + 1) % len(self._settings)
            self._ensure_visible()
        elif action == "TRIPLE_PRESS":
            self._selected = (self._selected - 1) % len(self._settings)
            self._ensure_visible()
        elif action == "DOUBLE_PRESS":
            setting = self._settings[self._selected]
            if setting.get("action"):
                self._run_action(setting["key"])
            elif "options" in setting:
                opts = setting["options"]
                try:
                    idx = opts.index(setting["value"])
                except ValueError:
                    idx = -1
                new_idx = (idx + 1) % len(opts)
                setting["value"] = opts[new_idx]
                # Convert on/off back to bool for boolean settings
                store_val = setting["value"]
                if setting["key"] in ("web_search", "memory", "extended_thinking"):
                    store_val = setting["value"] == "on"
                elif setting["key"] == "ai_model" and store_val == "default":
                    store_val = ""
                self._repository.set_setting(setting["key"], store_val)
                logger.info("setting_changed: %s=%s", setting["key"], store_val)
        elif action == "LONG_PRESS":
            if self._on_back:
                self._on_back()

    def _ensure_visible(self):
        """Scroll to keep selected item visible."""
        visible_items = self._visible_item_count()
        if self._selected < self._scroll_offset:
            self._scroll_offset = self._selected
        elif self._selected >= self._scroll_offset + visible_items:
            self._scroll_offset = self._selected - visible_items + 1

    def _visible_item_count(self) -> int:
        """How many settings items fit on screen."""
        available_h = PHYSICAL_H - SAFE_INSET - STATUS_BAR_H - 8 - SAFE_INSET - 20
        item_h = self._line_height * 2 + 4
        return max(1, int(available_h / item_h))

    def _run_action(self, key: str):
        if key == "_test_voice":
            self._test_voice_status = "connecting..."
            import threading
            threading.Thread(target=self._run_voice_test, daemon=True).start()

    def _run_voice_test(self):
        try:
            self._test_voice_status = "synthesizing..."
            from audio.tts_test import test_speechify_api
            api_result = test_speechify_api()
            if not api_result["ok"]:
                self._test_voice_status = f"FAIL: {api_result['detail'][:20]}"
                return

            self._test_voice_status = "playing..."
            from audio.tts_test import test_full_pipeline
            pipeline_result = test_full_pipeline()
            if pipeline_result["ok"]:
                self._test_voice_status = f"OK ({pipeline_result['duration_ms']}ms)"
            else:
                self._test_voice_status = f"FAIL: {pipeline_result['detail'][:20]}"
        except Exception as exc:
            logger.error("voice_test_failed: %s", exc)
            self._test_voice_status = f"ERROR: {str(exc)[:20]}"

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # Status bar
        header = self._font_small.render("CHAT SETTINGS", False, WHITE)
        surface.blit(header, (SAFE_INSET, SAFE_INSET + (STATUS_BAR_H - header.get_height()) // 2))
        pygame.draw.line(surface, HAIRLINE, (0, SAFE_INSET + STATUS_BAR_H - 1), (PHYSICAL_W, SAFE_INSET + STATUS_BAR_H - 1))

        # Settings list (scrollable)
        y = SAFE_INSET + STATUS_BAR_H + 8
        hint_y = PHYSICAL_H - SAFE_INSET - 20
        visible = self._visible_item_count()

        for idx in range(self._scroll_offset, min(len(self._settings), self._scroll_offset + visible)):
            if y + self._line_height > hint_y:
                break

            setting = self._settings[idx]
            selected = idx == self._selected
            label_color = WHITE if selected else DIM3
            value_color = DIM2

            prefix = "> " if selected else "  "
            label_surf = self._font.render(prefix + setting["label"], False, label_color)
            surface.blit(label_surf, (SAFE_INSET, y))
            y += self._line_height

            # Value display
            if setting["key"] == "_test_voice" and self._test_voice_status:
                val_text = self._test_voice_status
            else:
                val_text = setting["value"]
            if len(val_text) > 28:
                val_text = val_text[:25] + "..."
            val_surf = self._font_small.render(f'  "{val_text}"', False, value_color)
            surface.blit(val_surf, (SAFE_INSET, y))
            y += self._line_height + 4

        # Scroll indicators
        if self._scroll_offset > 0:
            up = self._font_small.render("\u25b2", False, DIM1)
            surface.blit(up, (PHYSICAL_W - 16, SAFE_INSET + STATUS_BAR_H + 4))
        if self._scroll_offset + visible < len(self._settings):
            down = self._font_small.render("\u25bc", False, DIM1)
            surface.blit(down, (PHYSICAL_W - 16, hint_y - 14))

        # Hint bar
        pygame.draw.line(surface, HAIRLINE, (0, hint_y), (PHYSICAL_W, hint_y))
        hint = self._font_small.render("tap:next \u00b7 dbl:change \u00b7 hold:back", False, DIM1)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, hint_y + 4))

    def update(self, dt: float):
        pass


def _to_bool(val) -> bool:
    """Convert various stored setting values to bool."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).lower()
    return s in ("true", "1", "yes", "on")
