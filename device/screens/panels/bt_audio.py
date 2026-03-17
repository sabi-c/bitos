"""Bluetooth Audio settings panel for BITOS device UI.

Provides device scanning, pairing, connecting, disconnecting, and forgetting
Bluetooth audio devices (headphones, speakers, AirPods).

UI flow:
    SETTINGS -> BT AUDIO -> status + action rows
        SCAN FOR DEVICES -> scanning animation -> device list
        Select device -> pair + connect
        DISCONNECT -> disconnect active device
        FORGET DEVICE -> unpair
"""
from __future__ import annotations

import pygame
import threading
import time

from display.theme import load_ui_font, merge_runtime_ui_settings
from display.tokens import BLACK, DIM2, DIM3, HAIRLINE, PHYSICAL_H, PHYSICAL_W, WHITE, STATUS_BAR_H, ROW_H_MIN
from screens.base import BaseScreen
from screens.components import NavItem, VerticalNavController


# Panel modes
_MODE_MAIN = "main"
_MODE_SCANNING = "scanning"
_MODE_RESULTS = "results"


class BluetoothAudioPanel(BaseScreen):
    """Bluetooth audio device management panel."""
    _owns_status_bar = True

    def __init__(self, bt_audio_manager, repository=None, on_back=None, ui_settings=None):
        self._bt = bt_audio_manager
        self._repo = repository
        self._on_back = on_back

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        self._mode = _MODE_MAIN
        self._connected_device: dict | None = None
        self._scan_results: list[dict] = []
        self._scan_start_time: float = 0.0
        self._status_message: str = ""
        self._status_timeout: float = 0.0
        self._scroll_offset = 0

        # Main menu nav
        self._nav = self._build_main_nav()

        # Results nav (rebuilt after scan)
        self._results_nav: VerticalNavController | None = None

    def _build_main_nav(self) -> VerticalNavController:
        """Build the main menu navigation items."""
        items = [
            NavItem(key="scan", label="SCAN FOR DEVICES", action=self._start_scan),
        ]
        if self._connected_device:
            items.append(NavItem(key="disconnect", label="DISCONNECT", action=self._do_disconnect))
            items.append(NavItem(key="forget", label="FORGET DEVICE", action=self._do_forget))
        items.append(NavItem(key="back", label="BACK", status="SETTINGS", action=self._go_back))
        return VerticalNavController(items)

    def on_enter(self):
        self._mode = _MODE_MAIN
        self._connected_device = self._bt.get_connected_device()
        self._nav = self._build_main_nav()
        self._scroll_offset = 0

    def handle_action(self, action: str):
        if self._mode == _MODE_SCANNING:
            # Allow cancelling scan with LONG_PRESS
            if action == "LONG_PRESS":
                self._mode = _MODE_MAIN
            return

        if self._mode == _MODE_RESULTS:
            self._handle_results_action(action)
            return

        # Main mode
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
        if self._mode == _MODE_SCANNING:
            if event.key == pygame.K_ESCAPE:
                self._mode = _MODE_MAIN
            return
        if self._mode == _MODE_RESULTS:
            self._handle_results_input(event)
            return
        # Main mode keyboard
        if event.key in (pygame.K_DOWN, pygame.K_j):
            self._nav.move(1)
        elif event.key in (pygame.K_UP, pygame.K_k):
            self._nav.move(-1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._nav.activate_focused()
        elif event.key == pygame.K_ESCAPE:
            self._go_back()

    def update(self, dt: float):
        # Check if async scan completed
        if self._mode == _MODE_SCANNING and not self._bt.is_scanning:
            self._scan_results = self._bt.get_scan_results()
            self._mode = _MODE_RESULTS
            self._results_nav = self._build_results_nav()
            self._scroll_offset = 0

        # Clear status message after timeout
        if self._status_message and time.monotonic() > self._status_timeout:
            self._status_message = ""

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # Status bar
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("BT AUDIO", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        if self._mode == _MODE_SCANNING:
            self._render_scanning(surface)
        elif self._mode == _MODE_RESULTS:
            self._render_results(surface)
        else:
            self._render_main(surface)

    def _render_main(self, surface: pygame.Surface):
        """Render main menu: status + action rows."""
        y = STATUS_BAR_H + 4

        # Connection status line
        if self._connected_device:
            status_text = self._connected_device.get("name", "Unknown")
            status_label = "CONNECTED"
            label_surf = self._font_small.render(status_label, False, DIM2)
            name_surf = self._font_body.render(status_text, False, WHITE)
            surface.blit(label_surf, (8, y))
            y += label_surf.get_height() + 2
            surface.blit(name_surf, (8, y))
            y += name_surf.get_height() + 4
        else:
            no_dev = self._font_body.render("NO DEVICE", False, DIM2)
            surface.blit(no_dev, (8, y))
            y += no_dev.get_height() + 4

        pygame.draw.line(surface, HAIRLINE, (0, y), (PHYSICAL_W, y))
        y += 4

        # Status message (temporary feedback)
        if self._status_message:
            msg_surf = self._font_small.render(self._status_message, False, DIM2)
            surface.blit(msg_surf, (8, y))
            y += msg_surf.get_height() + 4

        # Nav rows
        for idx, item in enumerate(self._nav.items):
            focused = idx == self._nav.focus_index
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

        # Hint
        hint = self._font_hint.render("SHORT:NEXT \u00b7 DBL:SELECT \u00b7 LONG:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    def _render_scanning(self, surface: pygame.Surface):
        """Render scanning animation."""
        y = STATUS_BAR_H + 20

        # Animated dots
        elapsed = time.monotonic() - self._scan_start_time
        dots = "." * (int(elapsed * 2) % 4)
        scan_text = f"SCANNING{dots}"
        scan_surf = self._font_body.render(scan_text, False, WHITE)
        surface.blit(scan_surf, ((PHYSICAL_W - scan_surf.get_width()) // 2, y))

        y += scan_surf.get_height() + 12

        # Show devices found so far
        partial = self._bt.get_scan_results()
        count_text = f"{len(partial)} DEVICE{'S' if len(partial) != 1 else ''} FOUND"
        count_surf = self._font_small.render(count_text, False, DIM2)
        surface.blit(count_surf, ((PHYSICAL_W - count_surf.get_width()) // 2, y))

        # Hint
        hint = self._font_hint.render("LONG:CANCEL", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    def _render_results(self, surface: pygame.Surface):
        """Render scan results list."""
        if not self._scan_results:
            y = STATUS_BAR_H + 20
            no_results = self._font_body.render("NO DEVICES FOUND", False, DIM2)
            surface.blit(no_results, ((PHYSICAL_W - no_results.get_width()) // 2, y))
            hint = self._font_hint.render("DBL:RESCAN \u00b7 LONG:BACK", False, DIM3)
            surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))
            return

        if not self._results_nav:
            return

        # Scrollable device list
        hint_h = 14
        viewport_top = STATUS_BAR_H
        viewport_bottom = PHYSICAL_H - hint_h
        viewport_h = viewport_bottom - viewport_top
        max_visible = viewport_h // ROW_H_MIN

        total = len(self._results_nav.items)
        focus = self._results_nav.focus_index
        if focus < self._scroll_offset:
            self._scroll_offset = focus
        elif focus >= self._scroll_offset + max_visible:
            self._scroll_offset = focus - max_visible + 1
        self._scroll_offset = max(0, min(self._scroll_offset, max(0, total - max_visible)))

        y = viewport_top
        for idx in range(self._scroll_offset, min(self._scroll_offset + max_visible, total)):
            item = self._results_nav.items[idx]
            focused = idx == self._results_nav.focus_index
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

        # Scroll indicators
        if self._scroll_offset > 0:
            arrow_up = self._font_hint.render("^", False, DIM3)
            surface.blit(arrow_up, (PHYSICAL_W - 12, viewport_top + 2))
        if self._scroll_offset + max_visible < total:
            arrow_dn = self._font_hint.render("v", False, DIM3)
            surface.blit(arrow_dn, (PHYSICAL_W - 12, viewport_bottom - 12))

        # Hint
        hint = self._font_hint.render("SHORT:NEXT \u00b7 DBL:PAIR \u00b7 LONG:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    # ------------------------------------------------------------------
    # Results mode navigation
    # ------------------------------------------------------------------

    def _build_results_nav(self) -> VerticalNavController:
        """Build nav items from scan results."""
        items = []
        for dev in self._scan_results:
            name = dev.get("name", "Unknown")
            address = dev.get("address", "")
            # Truncate long names for 240px display
            display_name = name[:22] if len(name) > 22 else name
            items.append(NavItem(
                key=address,
                label=display_name,
                status=address[-5:],  # Show last 5 chars of MAC
                action=lambda addr=address: self._pair_and_connect(addr),
            ))
        items.append(NavItem(key="back", label="BACK", status="", action=self._back_to_main))
        return VerticalNavController(items)

    def _handle_results_action(self, action: str):
        if not self._results_nav:
            return
        if action == "DOUBLE_PRESS":
            self._results_nav.activate_focused()
        elif action == "SHORT_PRESS":
            self._results_nav.move(1)
        elif action == "LONG_PRESS":
            self._back_to_main()
        elif action == "TRIPLE_PRESS":
            self._results_nav.move(-1)

    def _handle_results_input(self, event: pygame.event.Event):
        if not self._results_nav:
            return
        if event.key in (pygame.K_DOWN, pygame.K_j):
            self._results_nav.move(1)
        elif event.key in (pygame.K_UP, pygame.K_k):
            self._results_nav.move(-1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._results_nav.activate_focused()
        elif event.key == pygame.K_ESCAPE:
            self._back_to_main()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _start_scan(self):
        """Start async Bluetooth scan."""
        self._mode = _MODE_SCANNING
        self._scan_start_time = time.monotonic()
        self._bt.scan_async(timeout=10)

    def _pair_and_connect(self, address: str):
        """Pair and connect to a device in a background thread."""
        self._set_status("PAIRING...")
        self._mode = _MODE_MAIN

        def _worker():
            paired = self._bt.pair(address)
            if not paired:
                self._set_status("PAIR FAILED")
                return
            connected = self._bt.connect(address)
            if connected:
                self._set_status("CONNECTED")
                self._connected_device = self._bt.get_connected_device()
                self._nav = self._build_main_nav()
            else:
                self._set_status("CONNECT FAILED")

        threading.Thread(target=_worker, name="bt-pair", daemon=True).start()

    def _do_disconnect(self):
        """Disconnect current device."""
        if self._connected_device:
            address = self._connected_device.get("address")
            ok = self._bt.disconnect(address)
            if ok:
                self._set_status("DISCONNECTED")
                self._connected_device = None
                self._nav = self._build_main_nav()
            else:
                self._set_status("DISCONNECT FAILED")

    def _do_forget(self):
        """Forget (unpair) current device."""
        if self._connected_device:
            address = self._connected_device.get("address")
            ok = self._bt.forget(address)
            if ok:
                self._set_status("DEVICE FORGOTTEN")
                self._connected_device = None
                self._nav = self._build_main_nav()
            else:
                self._set_status("FORGET FAILED")

    def _back_to_main(self):
        self._mode = _MODE_MAIN
        self._scroll_offset = 0

    def _go_back(self):
        if self._on_back:
            self._on_back()

    def _set_status(self, message: str, duration: float = 3.0):
        """Show a temporary status message."""
        self._status_message = message
        self._status_timeout = time.monotonic() + duration
