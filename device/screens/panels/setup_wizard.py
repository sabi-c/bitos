"""BITOS first-boot setup wizard panel.

Multi-step guided setup: Welcome -> WiFi -> Pair Phone -> AirPods -> Volume -> All Set.
Shown on first boot when setup_complete is not set. Re-runnable from Settings.

UI flow:
    BOOT -> SETUP WIZARD -> 6 steps with progress dots
        Step 0: WELCOME — title + subtitle + DOUBLE to begin
        Step 1: CONNECT WI-FI — status + QR if needed
        Step 2: PAIR PHONE — BLE discoverable + QR + auto-advance
        Step 3: CONNECT AIRPODS — optional BT audio scan + pair
        Step 4: SPEAKER LEVEL — volume 0-100, SHORT +10, TRIPLE -10, DOUBLE confirm
        Step 5: ALL SET! — summary + DOUBLE to start
"""
from __future__ import annotations

import logging
import threading
import time

import pygame

from bluetooth.constants import PAIRING_MODE_TIMEOUT_SECONDS, build_pair_url, build_setup_url
from bluetooth.server import get_connected_companions
from display.theme import load_ui_font, merge_runtime_ui_settings
from display.tokens import (
    BLACK, DIM2, DIM3, HAIRLINE, PHYSICAL_H, PHYSICAL_W, WHITE, STATUS_BAR_H, ROW_H_MIN,
)
from overlays import QROverlay
from screens.base import BaseScreen
from screens.components import NavItem, VerticalNavController

logger = logging.getLogger(__name__)

_NUM_STEPS = 6

# Animation frames for discoverable status
_DISCOVERABLE_FRAMES = ["DISCOVERABLE", "DISCOVERABLE.", "DISCOVERABLE..", "DISCOVERABLE..."]

# Animation frames for scanning
_SCANNING_FRAMES = ["SCANNING", "SCANNING.", "SCANNING..", "SCANNING..."]


class SetupWizardPanel(BaseScreen):
    """Multi-step first-boot setup wizard."""
    _owns_status_bar = True

    def __init__(
        self,
        gatt_server,
        bt_audio_manager,
        auth_manager,
        repository,
        on_complete=None,
        on_push_overlay=None,
        on_dismiss_overlay=None,
        ui_settings: dict | None = None,
    ):
        self._gatt = gatt_server
        self._bt = bt_audio_manager
        self._auth = auth_manager
        self._repo = repository
        self._on_complete = on_complete
        self._on_push_overlay = on_push_overlay
        self._on_dismiss_overlay = on_dismiss_overlay

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        self._current_step = 0

        # Step completion tracking
        self._wifi_connected = False
        self._wifi_ssid = ""
        self._wifi_signal = ""
        self._phone_paired = False
        self._airpods_connected = False
        self._airpods_skipped = False

        # BLE pairing state
        self._pairing_active = False
        self._pairing_end: float = 0.0
        self._anim_frame = 0
        self._anim_tick: float = 0.0

        # Volume setting state
        self._volume = 50

        # BT audio scan state
        self._bt_scanning = False
        self._bt_scan_start: float = 0.0
        self._bt_scan_results: list[dict] = []
        self._bt_nav: VerticalNavController | None = None
        self._bt_status_message = ""
        self._bt_status_timeout: float = 0.0
        self._scroll_offset = 0

    def on_enter(self):
        self._refresh_wifi_status()

    def _refresh_wifi_status(self):
        """Check current WiFi status via the WiFi manager."""
        try:
            from bluetooth.wifi_manager import WiFiManager
            status = WiFiManager().get_status()
            self._wifi_connected = bool(status.get("connected"))
            self._wifi_ssid = str(status.get("ssid", ""))
            self._wifi_signal = str(status.get("signal", ""))
        except Exception:
            self._wifi_connected = False

    def handle_action(self, action: str):
        if self._current_step == 0:
            self._handle_step_welcome(action)
        elif self._current_step == 1:
            self._handle_step_wifi(action)
        elif self._current_step == 2:
            self._handle_step_pair(action)
        elif self._current_step == 3:
            self._handle_step_airpods(action)
        elif self._current_step == 4:
            self._handle_step_volume(action)
        elif self._current_step == 5:
            self._handle_step_done(action)

    def handle_input(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            return
        # Keyboard shortcuts for desktop testing
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.handle_action("DOUBLE_PRESS")
        elif event.key == pygame.K_RIGHT:
            self.handle_action("SHORT_PRESS")
        elif event.key == pygame.K_LEFT:
            self.handle_action("TRIPLE_PRESS")
        elif event.key == pygame.K_ESCAPE:
            self.handle_action("LONG_PRESS")

    def update(self, dt: float):
        now = time.time()

        # Step 2: check if companion connected (auto-advance)
        if self._current_step == 2 and self._pairing_active:
            if self._gatt.is_companion_connected():
                self._phone_paired = True
                self._pairing_active = False
                self._gatt.set_discoverable(False)
                self._current_step = 3
                return
            # Check pairing timeout
            if now > self._pairing_end:
                self._pairing_active = False
                self._gatt.set_discoverable(False)
            elif now - self._anim_tick > 0.5:
                self._anim_frame = (self._anim_frame + 1) % len(_DISCOVERABLE_FRAMES)
                self._anim_tick = now

        # Step 3: check if BT audio scan completed
        if self._current_step == 3 and self._bt_scanning:
            if not self._bt.is_scanning:
                self._bt_scanning = False
                self._bt_scan_results = self._bt.get_scan_results()
                self._bt_nav = self._build_bt_nav()
                self._scroll_offset = 0

        # Clear BT status message
        if self._bt_status_message and time.monotonic() > self._bt_status_timeout:
            self._bt_status_message = ""

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # Status bar
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("SETUP", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        # Step counter on right of status bar
        step_text = f"{self._current_step + 1}/{_NUM_STEPS}"
        step_surf = self._font_hint.render(step_text, False, BLACK)
        surface.blit(step_surf, (PHYSICAL_W - step_surf.get_width() - 6, (STATUS_BAR_H - step_surf.get_height()) // 2))

        # Progress dots below status bar
        self._render_progress_dots(surface)

        # Step content
        if self._current_step == 0:
            self._render_step_welcome(surface)
        elif self._current_step == 1:
            self._render_step_wifi(surface)
        elif self._current_step == 2:
            self._render_step_pair(surface)
        elif self._current_step == 3:
            self._render_step_airpods(surface)
        elif self._current_step == 4:
            self._render_step_volume(surface)
        elif self._current_step == 5:
            self._render_step_done(surface)

    # ------------------------------------------------------------------
    # Progress dots
    # ------------------------------------------------------------------

    def _render_progress_dots(self, surface: pygame.Surface):
        """Draw progress dots centered below the status bar."""
        dot_radius = 4
        dot_spacing = 16
        total_w = (_NUM_STEPS - 1) * dot_spacing
        start_x = (PHYSICAL_W - total_w) // 2
        y = STATUS_BAR_H + 10

        for i in range(_NUM_STEPS):
            x = start_x + i * dot_spacing
            if i < self._current_step:
                # Completed: filled white
                pygame.draw.circle(surface, WHITE, (x, y), dot_radius)
            elif i == self._current_step:
                # Current: filled white
                pygame.draw.circle(surface, WHITE, (x, y), dot_radius)
            else:
                # Future: dim outline
                pygame.draw.circle(surface, DIM3, (x, y), dot_radius, 1)

    # ------------------------------------------------------------------
    # Step 0: WELCOME
    # ------------------------------------------------------------------

    def _render_step_welcome(self, surface: pygame.Surface):
        y = STATUS_BAR_H + 60

        # "BITOS" title
        title = self._font_title.render("BITOS", False, WHITE)
        surface.blit(title, ((PHYSICAL_W - title.get_width()) // 2, y))
        y += title.get_height() + 20

        # Subtitle
        subtitle = self._font_body.render("LET'S GET SET UP", False, DIM2)
        surface.blit(subtitle, ((PHYSICAL_W - subtitle.get_width()) // 2, y))

        # Hint
        hint = self._font_hint.render("DOUBLE-PRESS TO BEGIN", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 8))

    def _handle_step_welcome(self, action: str):
        if action == "DOUBLE_PRESS":
            self._refresh_wifi_status()
            self._current_step = 1

    # ------------------------------------------------------------------
    # Step 1: CONNECT WI-FI
    # ------------------------------------------------------------------

    def _render_step_wifi(self, surface: pygame.Surface):
        y = STATUS_BAR_H + 30

        step_label = self._font_small.render("CONNECT WI-FI", False, DIM2)
        surface.blit(step_label, ((PHYSICAL_W - step_label.get_width()) // 2, y))
        y += step_label.get_height() + 16

        if self._wifi_connected:
            # Connected: show SSID + signal
            ssid_text = self._wifi_ssid or "CONNECTED"
            ssid_surf = self._font_body.render(ssid_text, False, WHITE)
            surface.blit(ssid_surf, ((PHYSICAL_W - ssid_surf.get_width()) // 2, y))
            y += ssid_surf.get_height() + 8

            signal_text = f"SIGNAL: {self._wifi_signal.upper()}"
            signal_surf = self._font_small.render(signal_text, False, DIM2)
            surface.blit(signal_surf, ((PHYSICAL_W - signal_surf.get_width()) // 2, y))
            y += signal_surf.get_height() + 20

            check = self._font_body.render("WI-FI CONNECTED", False, WHITE)
            surface.blit(check, ((PHYSICAL_W - check.get_width()) // 2, y))

            hint = self._font_hint.render("DBL:NEXT  LONG:BACK", False, DIM3)
            surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 8))
        else:
            # Not connected
            msg = self._font_body.render("NO WI-FI", False, DIM2)
            surface.blit(msg, ((PHYSICAL_W - msg.get_width()) // 2, y))
            y += msg.get_height() + 12

            help_text = self._font_small.render("CONNECT VIA", False, DIM3)
            surface.blit(help_text, ((PHYSICAL_W - help_text.get_width()) // 2, y))
            y += help_text.get_height() + 4
            help_text2 = self._font_small.render("COMPANION APP", False, DIM3)
            surface.blit(help_text2, ((PHYSICAL_W - help_text2.get_width()) // 2, y))

            hint = self._font_hint.render("DBL:SHOW QR  LONG:BACK", False, DIM3)
            surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 8))

    def _handle_step_wifi(self, action: str):
        if action == "DOUBLE_PRESS":
            if self._wifi_connected:
                self._current_step = 2
                self._start_pairing()
            else:
                self._show_wifi_qr()
        elif action == "SHORT_PRESS":
            # Refresh status
            self._refresh_wifi_status()
        elif action == "LONG_PRESS":
            self._current_step = 0

    def _show_wifi_qr(self):
        """Show QR code for WiFi setup via companion app."""
        if not self._on_push_overlay:
            return
        ble_addr = self._gatt.get_device_address()
        url = build_setup_url(ble_addr)

        def _on_dismiss():
            if self._on_dismiss_overlay:
                self._on_dismiss_overlay(qr)
            # Re-check WiFi after QR dismissed
            self._refresh_wifi_status()

        qr = QROverlay(
            url=url,
            title="WI-FI SETUP",
            subtitle="SCAN WITH YOUR PHONE",
            timeout_s=120,
            on_dismiss=_on_dismiss,
        )
        self._on_push_overlay(qr)
        # Enable BLE discoverable so companion can find us
        self._gatt.set_discoverable(True, timeout_s=120)

    # ------------------------------------------------------------------
    # Step 2: PAIR PHONE
    # ------------------------------------------------------------------

    def _render_step_pair(self, surface: pygame.Surface):
        y = STATUS_BAR_H + 30

        step_label = self._font_small.render("PAIR PHONE", False, DIM2)
        surface.blit(step_label, ((PHYSICAL_W - step_label.get_width()) // 2, y))
        y += step_label.get_height() + 16

        if self._phone_paired or self._gatt.is_companion_connected():
            # Already paired
            paired_text = self._font_body.render("COMPANION PAIRED", False, WHITE)
            surface.blit(paired_text, ((PHYSICAL_W - paired_text.get_width()) // 2, y))

            hint = self._font_hint.render("DBL:NEXT  LONG:BACK", False, DIM3)
            surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 8))
        elif self._pairing_active:
            # Discoverable with countdown
            remaining = max(0, int(self._pairing_end - time.time()))
            disc_text = _DISCOVERABLE_FRAMES[self._anim_frame]
            disc_surf = self._font_body.render(disc_text, False, WHITE)
            surface.blit(disc_surf, ((PHYSICAL_W - disc_surf.get_width()) // 2, y))
            y += disc_surf.get_height() + 8

            timer_text = f"{remaining}s REMAINING"
            timer_surf = self._font_small.render(timer_text, False, DIM2)
            surface.blit(timer_surf, ((PHYSICAL_W - timer_surf.get_width()) // 2, y))
            y += timer_surf.get_height() + 16

            scan_hint = self._font_small.render("SCAN QR TO PAIR", False, DIM3)
            surface.blit(scan_hint, ((PHYSICAL_W - scan_hint.get_width()) // 2, y))

            hint = self._font_hint.render("DBL:SHOW QR  LONG:SKIP", False, DIM3)
            surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 8))
        else:
            # Not pairing
            msg = self._font_body.render("PAIR YOUR PHONE", False, DIM2)
            surface.blit(msg, ((PHYSICAL_W - msg.get_width()) // 2, y))
            y += msg.get_height() + 12

            help_msg = self._font_small.render("DBL TO START PAIRING", False, DIM3)
            surface.blit(help_msg, ((PHYSICAL_W - help_msg.get_width()) // 2, y))

            hint = self._font_hint.render("DBL:PAIR  LONG:SKIP", False, DIM3)
            surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 8))

    def _handle_step_pair(self, action: str):
        if action == "DOUBLE_PRESS":
            if self._phone_paired or self._gatt.is_companion_connected():
                self._phone_paired = True
                self._current_step = 3
            elif self._pairing_active:
                self._show_pair_qr()
            else:
                self._start_pairing()
        elif action == "LONG_PRESS":
            # Skip pairing
            self._pairing_active = False
            self._gatt.set_discoverable(False)
            self._current_step = 3
        elif action == "SHORT_PRESS":
            # Next (advance if paired)
            if self._phone_paired or self._gatt.is_companion_connected():
                self._phone_paired = True
                self._current_step = 3

    def _start_pairing(self):
        """Enable BLE discoverable mode."""
        self._pairing_active = True
        self._pairing_end = time.time() + PAIRING_MODE_TIMEOUT_SECONDS
        self._anim_frame = 0
        self._anim_tick = time.time()
        self._gatt.set_discoverable(True, timeout_s=PAIRING_MODE_TIMEOUT_SECONDS)

    def _show_pair_qr(self):
        """Show QR code for companion app pairing."""
        if not self._on_push_overlay:
            return
        ble_addr = self._gatt.get_device_address()
        url, session_id, token, expires = build_pair_url(ble_addr)
        if self._auth:
            self._auth.pairing.start(session_id, token, expires)

        def _on_dismiss():
            if self._on_dismiss_overlay:
                self._on_dismiss_overlay(qr)

        qr = QROverlay(
            url=url,
            title="PAIR COMPANION",
            subtitle="SCAN WITH YOUR PHONE",
            on_dismiss=_on_dismiss,
        )
        self._on_push_overlay(qr)

    # ------------------------------------------------------------------
    # Step 3: CONNECT AIRPODS
    # ------------------------------------------------------------------

    def _render_step_airpods(self, surface: pygame.Surface):
        y = STATUS_BAR_H + 30

        step_label = self._font_small.render("BLUETOOTH AUDIO", False, DIM2)
        surface.blit(step_label, ((PHYSICAL_W - step_label.get_width()) // 2, y))
        y += step_label.get_height() + 16

        if self._airpods_connected:
            dev = self._bt.get_connected_device()
            name = dev.get("name", "CONNECTED") if dev else "CONNECTED"
            conn_surf = self._font_body.render(name, False, WHITE)
            surface.blit(conn_surf, ((PHYSICAL_W - conn_surf.get_width()) // 2, y))

            hint = self._font_hint.render("DBL:NEXT  LONG:BACK", False, DIM3)
            surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 8))
            return

        if self._bt_scanning:
            # Scanning animation
            elapsed = time.monotonic() - self._bt_scan_start
            dots = "." * (int(elapsed * 2) % 4)
            scan_text = f"SCANNING{dots}"
            scan_surf = self._font_body.render(scan_text, False, WHITE)
            surface.blit(scan_surf, ((PHYSICAL_W - scan_surf.get_width()) // 2, y))
            y += scan_surf.get_height() + 8

            partial = self._bt.get_scan_results()
            count_text = f"{len(partial)} FOUND"
            count_surf = self._font_small.render(count_text, False, DIM2)
            surface.blit(count_surf, ((PHYSICAL_W - count_surf.get_width()) // 2, y))

            hint = self._font_hint.render("LONG:SKIP", False, DIM3)
            surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 8))
            return

        if self._bt_nav:
            # Show scan results as nav items (always has RESCAN + SKIP)
            self._render_bt_results(surface, y)
            return

        # Initial state: offer to scan
        msg = self._font_body.render("CONNECT BT AUDIO?", False, WHITE)
        surface.blit(msg, ((PHYSICAL_W - msg.get_width()) // 2, y))
        y += msg.get_height() + 12

        sub = self._font_small.render("AIRPODS, SPEAKERS...", False, DIM3)
        surface.blit(sub, ((PHYSICAL_W - sub.get_width()) // 2, y))

        # Status message
        if self._bt_status_message:
            y += sub.get_height() + 16
            status_surf = self._font_small.render(self._bt_status_message, False, DIM2)
            surface.blit(status_surf, ((PHYSICAL_W - status_surf.get_width()) // 2, y))

        hint = self._font_hint.render("DBL:SCAN  LONG:SKIP", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 8))

    def _render_bt_results(self, surface: pygame.Surface, start_y: int):
        """Render BT audio scan results as a scrollable nav list."""
        if not self._bt_nav:
            return

        hint_h = 14
        viewport_top = start_y
        viewport_bottom = PHYSICAL_H - hint_h
        viewport_h = viewport_bottom - viewport_top
        max_visible = viewport_h // ROW_H_MIN

        total = len(self._bt_nav.items)
        focus = self._bt_nav.focus_index
        if focus < self._scroll_offset:
            self._scroll_offset = focus
        elif focus >= self._scroll_offset + max_visible:
            self._scroll_offset = focus - max_visible + 1
        self._scroll_offset = max(0, min(self._scroll_offset, max(0, total - max_visible)))

        y = viewport_top
        for idx in range(self._scroll_offset, min(self._scroll_offset + max_visible, total)):
            item = self._bt_nav.items[idx]
            focused = idx == self._bt_nav.focus_index
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

        hint = self._font_hint.render("SHORT:NEXT  DBL:PAIR  LONG:SKIP", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 8))

    def _handle_step_airpods(self, action: str):
        if self._airpods_connected:
            if action == "DOUBLE_PRESS":
                self._current_step = 4
            elif action == "LONG_PRESS":
                self._current_step = 2
            return

        if self._bt_scanning:
            if action == "LONG_PRESS":
                self._bt_scanning = False
                self._airpods_skipped = True
                self._current_step = 4
            return

        if self._bt_nav:
            # Navigating scan results
            if action == "SHORT_PRESS":
                self._bt_nav.move(1)
            elif action == "TRIPLE_PRESS":
                self._bt_nav.move(-1)
            elif action == "DOUBLE_PRESS":
                self._bt_nav.activate_focused()
            elif action == "LONG_PRESS":
                self._airpods_skipped = True
                self._current_step = 4
            return

        # Initial state
        if action == "DOUBLE_PRESS":
            self._start_bt_scan()
        elif action == "LONG_PRESS":
            self._airpods_skipped = True
            self._current_step = 4

    def _start_bt_scan(self):
        """Start async Bluetooth audio scan."""
        self._bt_scanning = True
        self._bt_scan_start = time.monotonic()
        self._bt_scan_results = []
        self._bt_nav = None
        self._bt.scan_async(timeout=10)

    def _build_bt_nav(self) -> VerticalNavController:
        """Build nav items from BT scan results."""
        items = []
        for dev in self._bt_scan_results:
            name = dev.get("name", "Unknown")
            address = dev.get("address", "")
            display_name = name[:22] if len(name) > 22 else name
            items.append(NavItem(
                key=address,
                label=display_name,
                status=address[-5:] if address else "",
                action=lambda addr=address: self._pair_bt_device(addr),
            ))
        items.append(NavItem(key="rescan", label="RESCAN", action=self._start_bt_scan))
        items.append(NavItem(key="skip", label="SKIP", action=self._skip_airpods))
        return VerticalNavController(items)

    def _pair_bt_device(self, address: str):
        """Pair and connect to a BT audio device in background."""
        self._set_bt_status("PAIRING...")
        # Clear nav while pairing so UI shows status message
        self._bt_nav = None

        def _worker():
            paired = self._bt.pair(address)
            if not paired:
                self._set_bt_status("PAIR FAILED — TRY AGAIN")
                # Rebuild nav so user can retry
                self._bt_nav = self._build_bt_nav()
                self._scroll_offset = 0
                return
            connected = self._bt.connect(address)
            if connected:
                self._airpods_connected = True
                self._set_bt_status("CONNECTED")
            else:
                self._set_bt_status("CONNECT FAILED — TRY AGAIN")
                # Rebuild nav so user can retry
                self._bt_nav = self._build_bt_nav()
                self._scroll_offset = 0

        threading.Thread(target=_worker, name="wizard-bt-pair", daemon=True).start()

    def _skip_airpods(self):
        self._airpods_skipped = True
        self._current_step = 4

    def _set_bt_status(self, message: str, duration: float = 3.0):
        self._bt_status_message = message
        self._bt_status_timeout = time.monotonic() + duration

    # ------------------------------------------------------------------
    # Step 4: SPEAKER LEVEL
    # ------------------------------------------------------------------

    def _render_step_volume(self, surface: pygame.Surface):
        y = STATUS_BAR_H + 30

        step_label = self._font_small.render("SPEAKER LEVEL", False, DIM2)
        surface.blit(step_label, ((PHYSICAL_W - step_label.get_width()) // 2, y))
        y += step_label.get_height() + 24

        # Volume number
        vol_text = f"{self._volume}%"
        vol_surf = self._font_title.render(vol_text, False, WHITE)
        surface.blit(vol_surf, ((PHYSICAL_W - vol_surf.get_width()) // 2, y))
        y += vol_surf.get_height() + 16

        # Volume bar
        bar_x = 24
        bar_w = PHYSICAL_W - 48
        bar_h = 8
        pygame.draw.rect(surface, DIM3, pygame.Rect(bar_x, y, bar_w, bar_h))
        fill_w = int(bar_w * self._volume / 100)
        if fill_w > 0:
            pygame.draw.rect(surface, WHITE, pygame.Rect(bar_x, y, fill_w, bar_h))

        hint = self._font_hint.render("SHORT:+  TRPL:-  DBL:OK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 8))

    def _handle_step_volume(self, action: str):
        if action == "SHORT_PRESS":
            self._volume = self._volume + 10 if self._volume < 100 else 0
        elif action == "TRIPLE_PRESS":
            self._volume = self._volume - 10 if self._volume > 0 else 100
        elif action == "DOUBLE_PRESS":
            self._repo.set_setting("volume", self._volume)
            logger.info("[SetupWizard] volume=%d", self._volume)
            self._current_step = 5
        elif action == "LONG_PRESS":
            self._current_step = 3

    # ------------------------------------------------------------------
    # Step 5: ALL SET!
    # ------------------------------------------------------------------

    def _render_step_done(self, surface: pygame.Surface):
        y = STATUS_BAR_H + 40

        title = self._font_title.render("ALL SET!", False, WHITE)
        surface.blit(title, ((PHYSICAL_W - title.get_width()) // 2, y))
        y += title.get_height() + 24

        # Checkmarks for completed steps
        steps = [
            ("WI-FI", self._wifi_connected),
            ("COMPANION", self._phone_paired or self._gatt.is_companion_connected()),
            ("BT AUDIO", self._airpods_connected),
            ("VOLUME", True),  # Always set (has default)
        ]

        for label, done in steps:
            mark = "[x]" if done else "[ ]"
            status = "DONE" if done else "SKIPPED"
            color = WHITE if done else DIM3

            row = self._font_body.render(f"{mark} {label}", False, color)
            surface.blit(row, (24, y))

            st = self._font_small.render(status, False, DIM2 if done else DIM3)
            surface.blit(st, (PHYSICAL_W - st.get_width() - 24, y + 2))
            y += row.get_height() + 10

        hint = self._font_hint.render("DOUBLE-PRESS TO START", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 8))

    def _handle_step_done(self, action: str):
        if action == "DOUBLE_PRESS":
            self._finish_wizard()
        elif action == "LONG_PRESS":
            self._current_step = 4

    def _finish_wizard(self):
        """Mark setup complete and fire on_complete callback."""
        self._repo.set_setting("setup_complete", True)
        logger.info("[SetupWizard] setup_complete=True")
        if self._on_complete:
            self._on_complete()
