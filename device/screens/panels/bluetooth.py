"""Bluetooth companion pairing panel for BITOS device UI.

Provides pairing mode activation, connected device listing, and status display.

UI flow:
    SETTINGS -> BLUETOOTH -> status + action rows
        PAIRING MODE -> enables discoverable for 120s with animated status
        CONNECTED DEVICES -> shows currently paired/connected companions
        Status line: "Discoverable" / "Connected: iPhone" / "Not connected"
"""
from __future__ import annotations

import pygame
import threading
import time

from bluetooth.constants import PAIRING_MODE_TIMEOUT_SECONDS, build_pair_url
from bluetooth.server import get_connected_companions
from display.theme import load_ui_font, merge_runtime_ui_settings
from display.tokens import BLACK, DIM2, DIM3, HAIRLINE, PHYSICAL_H, PHYSICAL_W, WHITE, STATUS_BAR_H, ROW_H_MIN
from overlays import QROverlay
from screens.base import BaseScreen
from screens.components import NavItem, VerticalNavController


# Animation frames for discoverable status
_DISCOVERABLE_FRAMES = ["DISCOVERABLE", "DISCOVERABLE.", "DISCOVERABLE..", "DISCOVERABLE..."]


class BluetoothPanel(BaseScreen):
    """Bluetooth companion connectivity panel."""
    _owns_status_bar = True

    def __init__(
        self,
        gatt_server,
        auth_manager=None,
        on_back=None,
        on_push_overlay=None,
        on_dismiss_overlay=None,
        ui_settings: dict | None = None,
    ):
        self._gatt = gatt_server
        self._auth_manager = auth_manager
        self._on_back = on_back
        self._on_push_overlay = on_push_overlay
        self._on_dismiss_overlay = on_dismiss_overlay

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        self._pairing_active = False
        self._pairing_end: float = 0.0
        self._anim_frame = 0
        self._anim_tick: float = 0.0
        self._connected_devices: list[dict] = []
        self._status_message = ""
        self._scroll_offset = 0

        self._nav = self._build_nav()

    def _build_nav(self) -> VerticalNavController:
        items = [
            NavItem(key="pairing", label="PAIRING MODE", status="", action=self._toggle_pairing),
            NavItem(key="pair_qr", label="PAIR WITH QR CODE", status="", action=self._show_pair_qr),
            NavItem(key="connected", label="CONNECTED DEVICES", status="", action=self._refresh_connected),
        ]
        # Add connected device rows
        for dev in self._connected_devices:
            name = dev.get("name", dev.get("address", "Unknown"))
            items.append(NavItem(key=f"dev_{dev.get('address', '')}", label=f"  {name}", status="", enabled=False))
        items.append(NavItem(key="back", label="BACK", status="SETTINGS", action=self._go_back))
        return VerticalNavController(items)

    def on_enter(self):
        self._scroll_offset = 0
        self._refresh_connected()
        # Check if still discoverable
        self._pairing_active = self._gatt.is_discoverable

    def handle_action(self, action: str):
        if action == "DOUBLE_PRESS":
            self._nav.activate_focused()
        elif action == "SHORT_PRESS":
            self._nav.move(1)
        elif action == "LONG_PRESS":
            self._go_back()
        elif action == "TRIPLE_PRESS":
            self._nav.move(-1)

    def handle_input(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_DOWN, pygame.K_j):
            self._nav.move(1)
        elif event.key in (pygame.K_UP, pygame.K_k):
            self._nav.move(-1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._nav.activate_focused()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # Status bar
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("BLUETOOTH", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        # Status indicator on right side of status bar
        status_text = self._get_status_text()
        status_surf = self._font_hint.render(status_text, False, BLACK)
        surface.blit(status_surf, (PHYSICAL_W - status_surf.get_width() - 6, (STATUS_BAR_H - status_surf.get_height()) // 2))

        # Update pairing animation
        now = time.time()
        if self._pairing_active:
            if now > self._pairing_end:
                self._pairing_active = False
                self._gatt.set_discoverable(False)
            elif now - self._anim_tick > 0.5:
                self._anim_frame = (self._anim_frame + 1) % len(_DISCOVERABLE_FRAMES)
                self._anim_tick = now

        # Update nav statuses
        statuses = {
            "pairing": _DISCOVERABLE_FRAMES[self._anim_frame] if self._pairing_active else "OFF",
            "pair_qr": "QR \u203a",
            "connected": f"{len(self._connected_devices)} DEVICE{'S' if len(self._connected_devices) != 1 else ''}",
            "back": "SETTINGS",
        }
        # Add device statuses
        for dev in self._connected_devices:
            addr = dev.get("address", "")
            statuses[f"dev_{addr}"] = ""

        # Scrollable rows
        hint_h = 14
        viewport_top = STATUS_BAR_H
        viewport_bottom = PHYSICAL_H - hint_h
        viewport_h = viewport_bottom - viewport_top
        max_visible = viewport_h // ROW_H_MIN

        total = len(self._nav.items)
        focus = self._nav.focus_index
        if focus < self._scroll_offset:
            self._scroll_offset = focus
        elif focus >= self._scroll_offset + max_visible:
            self._scroll_offset = focus - max_visible + 1
        self._scroll_offset = max(0, min(self._scroll_offset, total - max_visible))

        y = viewport_top
        for idx in range(self._scroll_offset, min(self._scroll_offset + max_visible, total)):
            item = self._nav.items[idx]
            focused = idx == self._nav.focus_index

            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            status_copy = statuses.get(item.key, item.status)
            row_color = BLACK if focused else WHITE
            status_color = BLACK if focused else DIM2
            indicator = "> " if focused else "- "
            row = self._font_body.render(indicator + item.label, False, row_color)
            status = self._font_small.render(status_copy, False, status_color)
            text_y = y + (ROW_H_MIN - row.get_height()) // 2
            surface.blit(row, (4, text_y))
            surface.blit(status, (PHYSICAL_W - status.get_width() - 8, text_y + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # Scroll indicators
        if self._scroll_offset > 0:
            arrow_up = self._font_hint.render("^", False, DIM3)
            surface.blit(arrow_up, (PHYSICAL_W - 12, viewport_top + 2))
        if self._scroll_offset + max_visible < total:
            arrow_dn = self._font_hint.render("v", False, DIM3)
            surface.blit(arrow_dn, (PHYSICAL_W - 12, viewport_bottom - 12))

        # Hint bar
        hint = self._font_hint.render("SHORT:NEXT \u00b7 DBL:OPEN \u00b7 LONG:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    def _get_status_text(self) -> str:
        if self._pairing_active:
            remaining = max(0, int(self._pairing_end - time.time()))
            return f"PAIR {remaining}s"
        if self._gatt.is_companion_connected():
            return "CONNECTED"
        if self._connected_devices:
            name = self._connected_devices[0].get("name", "device")
            # Truncate to fit
            if len(name) > 12:
                name = name[:11] + "\u2026"
            return name
        return "OFF"

    def _toggle_pairing(self):
        if self._pairing_active:
            # Turn off pairing
            self._pairing_active = False
            self._gatt.set_discoverable(False)
        else:
            # Enable pairing mode for 120 seconds
            self._pairing_active = True
            self._pairing_end = time.time() + PAIRING_MODE_TIMEOUT_SECONDS
            self._anim_frame = 0
            self._anim_tick = time.time()
            self._gatt.set_discoverable(True, timeout_s=PAIRING_MODE_TIMEOUT_SECONDS)

    def _show_pair_qr(self):
        if not self._on_push_overlay:
            return
        ble_addr = self._gatt.get_device_address()
        url, session_id, token, expires = build_pair_url(ble_addr)
        if self._auth_manager:
            self._auth_manager.pairing.start(session_id, token, expires)
        qr = QROverlay(
            url=url,
            title="PAIR COMPANION APP",
            subtitle="SCAN WITH YOUR PHONE",
            on_dismiss=lambda: self._on_dismiss_overlay(qr) if self._on_dismiss_overlay else None,
        )
        self._on_push_overlay(qr)
        # Also enable discoverable so the device can be found
        if not self._pairing_active:
            self._pairing_active = True
            self._pairing_end = time.time() + PAIRING_MODE_TIMEOUT_SECONDS
            self._anim_frame = 0
            self._anim_tick = time.time()
            self._gatt.set_discoverable(True, timeout_s=PAIRING_MODE_TIMEOUT_SECONDS)

    def _refresh_connected(self):
        self._connected_devices = get_connected_companions()
        self._nav = self._build_nav()

    def _go_back(self):
        if self._on_back:
            self._on_back()
