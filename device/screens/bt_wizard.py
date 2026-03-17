"""Bluetooth Pairing Wizard screen for BITOS OLED display.

Guided flow for scanning, selecting, and pairing Bluetooth audio devices.
Uses the BTService async backend for actual BT operations.

States: MENU -> SCANNING -> SELECT_DEVICE -> PAIRING -> CONNECTED -> DONE

Navigation: SHORT=next, DOUBLE=select, LONG=back
"""
from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame

from display.theme import load_ui_font, merge_runtime_ui_settings
from display.tokens import (
    BLACK, DIM2, DIM3, HAIRLINE, PHYSICAL_H, PHYSICAL_W, WHITE,
    STATUS_BAR_H, ROW_H_MIN,
)
from screens.base import BaseScreen
from screens.components import NavItem, VerticalNavController

if TYPE_CHECKING:
    from bluetooth.bt_service import BTService, BTDeviceInfo

logger = logging.getLogger(__name__)


class WizardState(Enum):
    MENU = auto()
    SCANNING = auto()
    SELECT_DEVICE = auto()
    PAIRING = auto()
    CONNECTED = auto()
    FAILED = auto()


class BTWizardScreen(BaseScreen):
    """Bluetooth pairing wizard with guided OLED flow.

    Designed for 240x280 display with single-button navigation.
    """
    SCREEN_NAME = "BT_WIZARD"
    _owns_status_bar = True

    def __init__(
        self,
        bt_service: BTService | None = None,
        on_back=None,
        on_device_connected=None,
        ui_settings=None,
    ):
        super().__init__()
        self._bt = bt_service
        self._on_back = on_back
        self._on_device_connected = on_device_connected

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        self._state = WizardState.MENU
        self._found_devices: list[BTDeviceInfo] = []
        self._selected_device: BTDeviceInfo | None = None
        self._scan_start_time: float = 0.0
        self._error_message: str = ""
        self._scroll_offset = 0

        # Connected device info (for success screen)
        self._connected_info: dict | None = None

        # Menu nav
        self._menu_nav = self._build_menu_nav()

        # Device list nav (rebuilt after scan)
        self._device_nav: VerticalNavController | None = None

        # Connected screen nav
        self._connected_nav: VerticalNavController | None = None

        # Async scan task handle
        self._scan_task: asyncio.Task | None = None
        self._pair_task: asyncio.Task | None = None

    def _build_menu_nav(self) -> VerticalNavController:
        items = [
            NavItem(key="scan", label="SCAN FOR DEVICES", action=self._start_scan),
            NavItem(key="paired", label="PAIRED DEVICES", action=self._show_paired),
            NavItem(key="back", label="BACK", action=self._go_back),
        ]
        return VerticalNavController(items)

    def _build_device_nav(self) -> VerticalNavController:
        items = []
        for dev in self._found_devices:
            display_name = dev.name[:20] if len(dev.name) > 20 else dev.name
            rssi_str = f"{dev.rssi}dBm" if dev.rssi else ""
            items.append(NavItem(
                key=dev.address,
                label=display_name,
                status=rssi_str,
                action=lambda d=dev: self._start_pairing(d),
            ))
        items.append(NavItem(key="rescan", label="RESCAN", action=self._start_scan))
        items.append(NavItem(key="back", label="BACK", action=self._back_to_menu))
        return VerticalNavController(items)

    def _build_connected_nav(self) -> VerticalNavController:
        items = [
            NavItem(key="done", label="DONE", action=self._finish),
            NavItem(key="forget", label="FORGET DEVICE", action=self._forget_device),
            NavItem(key="back", label="BACK", action=self._back_to_menu),
        ]
        return VerticalNavController(items)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self):
        self._state = WizardState.MENU
        self._menu_nav = self._build_menu_nav()
        self._scroll_offset = 0

    def on_exit(self):
        # Cancel any running async tasks
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
        if self._pair_task and not self._pair_task.done():
            self._pair_task.cancel()

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def handle_event(self, event) -> bool:
        """Handle ButtonEvent enum from button handler."""
        from input.handler import ButtonEvent
        action_map = {
            ButtonEvent.SHORT_PRESS: "SHORT_PRESS",
            ButtonEvent.DOUBLE_PRESS: "DOUBLE_PRESS",
            ButtonEvent.LONG_PRESS: "LONG_PRESS",
            ButtonEvent.TRIPLE_PRESS: "TRIPLE_PRESS",
        }
        action = action_map.get(event)
        if action:
            self.handle_action(action)
            return True
        return False

    def handle_action(self, action: str):
        if self._state == WizardState.MENU:
            self._handle_menu_action(action)
        elif self._state == WizardState.SCANNING:
            if action == "LONG_PRESS":
                self._cancel_scan()
        elif self._state == WizardState.SELECT_DEVICE:
            self._handle_select_action(action)
        elif self._state == WizardState.PAIRING:
            if action == "LONG_PRESS":
                self._back_to_menu()
        elif self._state == WizardState.CONNECTED:
            self._handle_connected_action(action)
        elif self._state == WizardState.FAILED:
            if action == "DOUBLE_PRESS":
                # Retry
                if self._selected_device:
                    self._start_pairing(self._selected_device)
            elif action == "LONG_PRESS":
                self._back_to_menu()

    def _handle_menu_action(self, action: str):
        if action == "DOUBLE_PRESS":
            self._menu_nav.activate_focused()
        elif action == "SHORT_PRESS":
            self._menu_nav.move(1)
        elif action == "LONG_PRESS":
            self._go_back()
        elif action == "TRIPLE_PRESS":
            self._menu_nav.move(-1)

    def _handle_select_action(self, action: str):
        if not self._device_nav:
            return
        if action == "DOUBLE_PRESS":
            self._device_nav.activate_focused()
        elif action == "SHORT_PRESS":
            self._device_nav.move(1)
        elif action == "LONG_PRESS":
            self._back_to_menu()
        elif action == "TRIPLE_PRESS":
            self._device_nav.move(-1)

    def _handle_connected_action(self, action: str):
        if not self._connected_nav:
            return
        if action == "DOUBLE_PRESS":
            self._connected_nav.activate_focused()
        elif action == "SHORT_PRESS":
            self._connected_nav.move(1)
        elif action == "LONG_PRESS":
            self._finish()
        elif action == "TRIPLE_PRESS":
            self._connected_nav.move(-1)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _start_scan(self):
        self._state = WizardState.SCANNING
        self._scan_start_time = time.monotonic()
        self._found_devices = []

        if self._bt and self._bt.is_available:
            loop = asyncio.get_event_loop()
            self._scan_task = loop.create_task(self._async_scan())
        else:
            # No BT available — transition to empty results after brief delay
            logger.warning("[BT-WIZARD] BT service not available")
            self._state = WizardState.SELECT_DEVICE
            self._device_nav = self._build_device_nav()

    async def _async_scan(self):
        try:
            devices = await self._bt.discover(timeout=15)
            # Filter to audio devices
            self._found_devices = [d for d in devices if d.is_audio]
            if not self._found_devices:
                # Show all devices if no audio ones found
                self._found_devices = devices
        except Exception as exc:
            logger.error("[BT-WIZARD] Scan error: %s", exc)
        finally:
            self._state = WizardState.SELECT_DEVICE
            self._device_nav = self._build_device_nav()
            self._scroll_offset = 0

    def _cancel_scan(self):
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
        self._state = WizardState.MENU

    def _start_pairing(self, device):
        self._selected_device = device
        self._state = WizardState.PAIRING
        self._error_message = ""

        if self._bt and self._bt.is_available:
            loop = asyncio.get_event_loop()
            self._pair_task = loop.create_task(self._async_pair(device))
        else:
            self._state = WizardState.FAILED
            self._error_message = "BT NOT AVAILABLE"

    async def _async_pair(self, device):
        try:
            success = await self._bt.pair_and_connect(device.address)
            if success:
                self._state = WizardState.CONNECTED
                self._connected_info = device.to_dict()
                self._connected_nav = self._build_connected_nav()

                if self._on_device_connected:
                    self._on_device_connected(device)
            else:
                self._state = WizardState.FAILED
                self._error_message = "PAIRING FAILED"
        except Exception as exc:
            logger.error("[BT-WIZARD] Pair error: %s", exc)
            self._state = WizardState.FAILED
            self._error_message = str(exc)[:30]

    def _forget_device(self):
        if self._selected_device and self._bt:
            loop = asyncio.get_event_loop()
            loop.create_task(self._bt.forget(self._selected_device.address))
            self._back_to_menu()

    def _show_paired(self):
        """Show already-paired devices as the scan result list."""
        if self._bt:
            self._found_devices = [
                d for d in self._bt.known_devices.values()
                if d.paired
            ]
        else:
            self._found_devices = []
        self._state = WizardState.SELECT_DEVICE
        self._device_nav = self._build_device_nav()
        self._scroll_offset = 0

    def _finish(self):
        self._go_back()

    def _back_to_menu(self):
        self._state = WizardState.MENU
        self._menu_nav = self._build_menu_nav()
        self._scroll_offset = 0

    def _go_back(self):
        if self._on_back:
            self._on_back()
        elif self._manager:
            self._manager.pop()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def update(self, dt: float):
        pass  # State transitions handled by async callbacks

    def draw(self, surface: pygame.Surface):
        self.render(surface)

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # Status bar
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title_text = "BLUETOOTH SETUP"
        if self._state == WizardState.SCANNING:
            title_text = "SCANNING"
        elif self._state == WizardState.PAIRING:
            title_text = "PAIRING"
        elif self._state == WizardState.CONNECTED:
            title_text = "CONNECTED"
        title = self._font_small.render(title_text, False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        if self._state == WizardState.MENU:
            self._render_menu(surface)
        elif self._state == WizardState.SCANNING:
            self._render_scanning(surface)
        elif self._state == WizardState.SELECT_DEVICE:
            self._render_device_list(surface)
        elif self._state == WizardState.PAIRING:
            self._render_pairing(surface)
        elif self._state == WizardState.CONNECTED:
            self._render_connected(surface)
        elif self._state == WizardState.FAILED:
            self._render_failed(surface)

    def _render_menu(self, surface: pygame.Surface):
        y = STATUS_BAR_H + 8

        # Show current BT status
        if self._bt and self._bt.connected_device:
            dev = self._bt.connected_device
            label = self._font_small.render("CONNECTED TO", False, DIM2)
            name = self._font_body.render(dev.name[:22], False, WHITE)
            surface.blit(label, (8, y))
            y += label.get_height() + 2
            surface.blit(name, (8, y))
            y += name.get_height() + 6
        else:
            no_dev = self._font_body.render("NO BT DEVICE", False, DIM2)
            surface.blit(no_dev, (8, y))
            y += no_dev.get_height() + 6

        pygame.draw.line(surface, HAIRLINE, (0, y), (PHYSICAL_W, y))
        y += 4

        # Nav rows
        self._render_nav(surface, self._menu_nav, y)

        # Hint
        self._render_hint(surface, "SHORT:NEXT \u00b7 DBL:SELECT \u00b7 LONG:BACK")

    def _render_scanning(self, surface: pygame.Surface):
        y = STATUS_BAR_H + 30

        elapsed = time.monotonic() - self._scan_start_time
        dots = "." * (int(elapsed * 2) % 4)
        scan_text = f"SCANNING{dots}"
        scan_surf = self._font_body.render(scan_text, False, WHITE)
        surface.blit(scan_surf, ((PHYSICAL_W - scan_surf.get_width()) // 2, y))

        y += scan_surf.get_height() + 16

        count = len(self._found_devices)
        count_text = f"{count} DEVICE{'S' if count != 1 else ''} FOUND"
        count_surf = self._font_small.render(count_text, False, DIM2)
        surface.blit(count_surf, ((PHYSICAL_W - count_surf.get_width()) // 2, y))

        self._render_hint(surface, "LONG:CANCEL")

    def _render_device_list(self, surface: pygame.Surface):
        if not self._found_devices:
            y = STATUS_BAR_H + 30
            no_results = self._font_body.render("NO DEVICES FOUND", False, DIM2)
            surface.blit(no_results, ((PHYSICAL_W - no_results.get_width()) // 2, y))
            self._render_hint(surface, "DBL:RESCAN \u00b7 LONG:BACK")
            return

        if not self._device_nav:
            return

        self._render_nav_scrollable(surface, self._device_nav, STATUS_BAR_H)
        self._render_hint(surface, "SHORT:NEXT \u00b7 DBL:PAIR \u00b7 LONG:BACK")

    def _render_pairing(self, surface: pygame.Surface):
        y = STATUS_BAR_H + 30

        connecting = self._font_body.render("CONNECTING TO", False, DIM2)
        surface.blit(connecting, ((PHYSICAL_W - connecting.get_width()) // 2, y))
        y += connecting.get_height() + 8

        if self._selected_device:
            name = self._selected_device.name[:22]
            name_surf = self._font_body.render(name, False, WHITE)
            surface.blit(name_surf, ((PHYSICAL_W - name_surf.get_width()) // 2, y))
            y += name_surf.get_height() + 16

        # Animated spinner
        elapsed = time.monotonic() - self._scan_start_time
        spinner = ["|", "/", "-", "\\"][int(elapsed * 4) % 4]
        spin_surf = self._font_title.render(spinner, False, DIM2)
        surface.blit(spin_surf, ((PHYSICAL_W - spin_surf.get_width()) // 2, y))

        self._render_hint(surface, "LONG:CANCEL")

    def _render_connected(self, surface: pygame.Surface):
        y = STATUS_BAR_H + 8

        # Success indicator
        ok = self._font_title.render("CONNECTED", False, WHITE)
        surface.blit(ok, ((PHYSICAL_W - ok.get_width()) // 2, y))
        y += ok.get_height() + 8

        if self._connected_info:
            name = self._connected_info.get("name", "Unknown")[:22]
            name_surf = self._font_body.render(name, False, WHITE)
            surface.blit(name_surf, ((PHYSICAL_W - name_surf.get_width()) // 2, y))
            y += name_surf.get_height() + 4

            addr = self._connected_info.get("address", "")
            addr_surf = self._font_small.render(addr, False, DIM2)
            surface.blit(addr_surf, ((PHYSICAL_W - addr_surf.get_width()) // 2, y))
            y += addr_surf.get_height() + 4

            if self._connected_info.get("is_airpods"):
                airpods_label = self._font_small.render("AIRPODS DETECTED", False, DIM2)
                surface.blit(airpods_label, ((PHYSICAL_W - airpods_label.get_width()) // 2, y))
                y += airpods_label.get_height() + 4

        y += 8
        pygame.draw.line(surface, HAIRLINE, (0, y), (PHYSICAL_W, y))
        y += 4

        if self._connected_nav:
            self._render_nav(surface, self._connected_nav, y)

        self._render_hint(surface, "SHORT:NEXT \u00b7 DBL:SELECT \u00b7 LONG:DONE")

    def _render_failed(self, surface: pygame.Surface):
        y = STATUS_BAR_H + 30

        fail = self._font_title.render("FAILED", False, WHITE)
        surface.blit(fail, ((PHYSICAL_W - fail.get_width()) // 2, y))
        y += fail.get_height() + 12

        if self._error_message:
            err_surf = self._font_small.render(self._error_message, False, DIM2)
            surface.blit(err_surf, ((PHYSICAL_W - err_surf.get_width()) // 2, y))
            y += err_surf.get_height() + 8

        if self._selected_device:
            name = self._selected_device.name[:22]
            name_surf = self._font_body.render(name, False, DIM2)
            surface.blit(name_surf, ((PHYSICAL_W - name_surf.get_width()) // 2, y))

        self._render_hint(surface, "DBL:RETRY \u00b7 LONG:BACK")

    # ------------------------------------------------------------------
    # Render helpers
    # ------------------------------------------------------------------

    def _render_nav(self, surface: pygame.Surface, nav: VerticalNavController, y: int):
        """Render nav items starting at y coordinate."""
        for idx, item in enumerate(nav.items):
            focused = idx == nav.focus_index
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            row_color = BLACK if focused else WHITE
            indicator = "> " if focused else "- "
            row = self._font_body.render(indicator + item.label, False, row_color)
            text_y = y + (ROW_H_MIN - row.get_height()) // 2
            surface.blit(row, (4, text_y))
            if item.status:
                status_color = BLACK if focused else DIM2
                st = self._font_small.render(item.status, False, status_color)
                surface.blit(st, (PHYSICAL_W - st.get_width() - 8, text_y + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

    def _render_nav_scrollable(self, surface: pygame.Surface, nav: VerticalNavController, top_y: int):
        """Render a scrollable nav list."""
        hint_h = 14
        viewport_bottom = PHYSICAL_H - hint_h
        viewport_h = viewport_bottom - top_y
        max_visible = viewport_h // ROW_H_MIN

        total = len(nav.items)
        focus = nav.focus_index
        if focus < self._scroll_offset:
            self._scroll_offset = focus
        elif focus >= self._scroll_offset + max_visible:
            self._scroll_offset = focus - max_visible + 1
        self._scroll_offset = max(0, min(self._scroll_offset, max(0, total - max_visible)))

        y = top_y
        for idx in range(self._scroll_offset, min(self._scroll_offset + max_visible, total)):
            item = nav.items[idx]
            focused = idx == nav.focus_index
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            row_color = BLACK if focused else WHITE
            indicator = "> " if focused else "- "
            row = self._font_body.render(indicator + item.label, False, row_color)
            text_y = y + (ROW_H_MIN - row.get_height()) // 2
            surface.blit(row, (4, text_y))
            if item.status:
                status_color = BLACK if focused else DIM2
                st = self._font_small.render(item.status, False, status_color)
                surface.blit(st, (PHYSICAL_W - st.get_width() - 8, text_y + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # Scroll arrows
        if self._scroll_offset > 0:
            arrow = self._font_hint.render("^", False, DIM3)
            surface.blit(arrow, (PHYSICAL_W - 12, top_y + 2))
        if self._scroll_offset + max_visible < total:
            arrow = self._font_hint.render("v", False, DIM3)
            surface.blit(arrow, (PHYSICAL_W - 12, viewport_bottom - 12))

    def _render_hint(self, surface: pygame.Surface, text: str):
        hint = self._font_hint.render(text, False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    def get_hint(self) -> str:
        if self._state == WizardState.SCANNING:
            return "[hold] cancel"
        if self._state == WizardState.PAIRING:
            return "[hold] cancel"
        if self._state == WizardState.FAILED:
            return "[2x] retry  [hold] back"
        return "[tap] scroll  [2x] select  [hold] back"
