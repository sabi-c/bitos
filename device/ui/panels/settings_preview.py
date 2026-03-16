"""SettingsPreviewPanel — device info header + quick-change items + open settings.

Top area: device name, battery, WiFi status, agent mode.
Below: 3 quick-toggle items (cycle inline) + OPEN SETTINGS + BACK.
"""

from __future__ import annotations

import pygame

from device.display.theme import get_font
from device.display.tokens import WHITE, DIM2, DIM3, HAIRLINE
from device.ui.panels.base import PreviewPanel


HEADER_H = 44
HEADER_FONT = 10
INFO_FONT = 8
PAD_X = 6
PAD_Y = 4
LINE_H = 14

# Cycle values for quick toggles
VOICE_OPTIONS = ["off", "on", "auto"]
AGENT_MODE_OPTIONS = ["producer", "hacker", "clown", "monk", "storyteller", "director"]
VOLUME_OPTIONS = [0, 25, 50, 75, 100]

SETTINGS_ITEMS = [
    {"label": "VOICE MODE", "description": "Toggle voice on/off", "action": "toggle_voice"},
    {"label": "AGENT MODE", "description": "Switch agent personality", "action": "toggle_mode"},
    {"label": "VOLUME", "description": "Adjust volume", "action": "toggle_volume"},
    {"label": "OPEN SETTINGS", "description": "Full settings panel", "action": "open"},
    {"label": "BACK", "description": "Return to sidebar", "action": "back"},
]

# Actions that cycle inline instead of opening the full panel
_TOGGLE_ACTIONS = {"toggle_voice", "toggle_mode", "toggle_volume"}


class SettingsPreviewPanel(PreviewPanel):
    """Preview panel for SETTINGS sidebar item."""

    def __init__(self, on_action: callable, status_state=None, repository=None):
        super().__init__(items=SETTINGS_ITEMS, on_action=on_action)
        self._status_state = status_state
        self._repository = repository
        self._refresh_labels()

    def on_enter(self) -> None:
        """Called when the panel becomes active — refresh labels from repository."""
        self._refresh_labels()

    # ── Inline cycling ──────────────────────────────────────────────

    def _refresh_labels(self):
        """Update item labels to reflect current persisted values."""
        if not self._repository:
            return
        voice = str(self._repository.get_setting("voice_mode", "off")).lower()
        mode = str(self._repository.get_setting("agent_mode", "producer")).lower()
        vol = int(self._repository.get_setting("volume", 75))
        self.items[0]["label"] = f"VOICE: {voice.upper()}"
        self.items[1]["label"] = f"MODE: {mode.upper()}"
        self.items[2]["label"] = f"VOL: {vol}%"

    def _cycle_voice(self):
        cur = str(self._repository.get_setting("voice_mode", "off")).lower()
        idx = VOICE_OPTIONS.index(cur) if cur in VOICE_OPTIONS else 0
        nxt = VOICE_OPTIONS[(idx + 1) % len(VOICE_OPTIONS)]
        self._repository.set_setting("voice_mode", nxt)
        self._refresh_labels()

    def _cycle_agent_mode(self):
        cur = str(self._repository.get_setting("agent_mode", "producer")).lower()
        idx = AGENT_MODE_OPTIONS.index(cur) if cur in AGENT_MODE_OPTIONS else 0
        nxt = AGENT_MODE_OPTIONS[(idx + 1) % len(AGENT_MODE_OPTIONS)]
        self._repository.set_setting("agent_mode", nxt)
        self._refresh_labels()

    def _cycle_volume(self):
        cur = int(self._repository.get_setting("volume", 75))
        idx = VOLUME_OPTIONS.index(cur) if cur in VOLUME_OPTIONS else 0
        nxt = VOLUME_OPTIONS[(idx + 1) % len(VOLUME_OPTIONS)]
        self._repository.set_setting("volume", nxt)
        self._refresh_labels()

    # ── Action override ─────────────────────────────────────────────

    def handle_action(self, action: str) -> bool:
        """Intercept DOUBLE_PRESS on toggle items to cycle inline."""
        if action == "DOUBLE_PRESS" and self.selected_index >= 0:
            item = self.items[self.selected_index]
            act = item["action"]
            if act in _TOGGLE_ACTIONS and self._repository:
                if act == "toggle_voice":
                    self._cycle_voice()
                elif act == "toggle_mode":
                    self._cycle_agent_mode()
                elif act == "toggle_volume":
                    self._cycle_volume()
                return True
        # Fall through to base for SHORT_PRESS navigation and non-toggle DOUBLE_PRESS
        result = super().handle_action(action)
        self._refresh_labels()
        return result

    # ── Render ──────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface) -> None:
        w = surface.get_width()
        header_font = get_font(HEADER_FONT)
        info_font = get_font(INFO_FONT)

        # ── Header: device status summary ──
        y = PAD_Y
        header_surf = header_font.render("DEVICE", False, WHITE)
        surface.blit(header_surf, (PAD_X, y))
        y += LINE_H + 2

        # Status lines
        lines = []
        if self._status_state:
            batt = getattr(self._status_state, "battery_text", "??%")
            lines.append(f"BAT: {batt}")
            wifi = getattr(self._status_state, "wifi_ssid", None)
            if wifi:
                lines.append(f"NET: {wifi}")
            else:
                lines.append("NET: --")
        else:
            lines = ["BAT: ??%", "NET: --"]

        for line in lines:
            surf = info_font.render(line, False, DIM3)
            surface.blit(surf, (PAD_X, y))
            y += LINE_H

        # Separator
        sep_y = HEADER_H - 1
        pygame.draw.line(surface, HAIRLINE,
                         (PAD_X, sep_y), (w - PAD_X, sep_y))

        # ── Submenu items ──
        self._render_items(surface, y_offset=HEADER_H)
