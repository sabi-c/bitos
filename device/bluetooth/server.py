"""BlueZ GATT server shell with desktop-safe mock fallback."""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from .constants import PAIRING_MODE_TIMEOUT_SECONDS

try:
    import dbus  # type: ignore
    import dbus.service  # type: ignore

    _BLUEZ_AVAILABLE = True
except ImportError:  # pragma: no cover
    dbus = None
    _BLUEZ_AVAILABLE = False


class BitosGATTServer:
    """BlueZ-backed GATT server skeleton (wiring intentionally minimal this sprint)."""

    def __init__(
        self,
        auth_manager,
        on_wifi_config=None,
        on_keyboard_input=None,
        on_settings_write=None,
        on_pin_change=None,
        on_reboot=None,
        on_show_passkey=None,
        on_pairing_complete=None,
        device_info_characteristic=None,
    ):
        self._auth_manager = auth_manager
        self._on_wifi_config = on_wifi_config
        self._on_keyboard_input = on_keyboard_input
        self._on_settings_write = on_settings_write
        self._on_pin_change = on_pin_change
        self._on_reboot = on_reboot
        self._on_show_passkey = on_show_passkey
        self._on_pairing_complete = on_pairing_complete
        self._device_info_characteristic = device_info_characteristic
        self._running = False
        self._thread: threading.Thread | None = None
        self._discoverable = False
        self._pairing_until = 0.0
        self._companion_connected = False
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="bitos-gatt", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def set_discoverable(self, enabled: bool, timeout_s: int = PAIRING_MODE_TIMEOUT_SECONDS) -> None:
        self._discoverable = bool(enabled)
        if enabled:
            self._pairing_until = time.time() + max(1, int(timeout_s))
        else:
            self._pairing_until = 0.0

    def notify_device_status(self, status: dict) -> None:
        logging.info("[BLE] notify device status: %s", status)

    def notify_notification_relay(self, notif: dict) -> None:
        logging.info("[BLE] relay notification: %s", notif)

    def is_companion_connected(self) -> bool:
        return self._companion_connected

    def get_device_address(self) -> str:
        return os.environ.get("BITOS_BLE_ADDRESS", "AA:BB:CC:DD:EE:FF")

    def _loop(self) -> None:
        while self._running:
            try:
                if self._discoverable and self._pairing_until and time.time() >= self._pairing_until:
                    self.set_discoverable(False)
            except Exception as exc:
                logging.error("[BLE] GATT server loop error: %s", exc)
            self._stop_event.wait(timeout=0.2)


class MockGATTServer:
    """No-op GATT server used in non-BlueZ environments and tests."""

    def __init__(
        self,
        auth_manager,
        on_wifi_config=None,
        on_keyboard_input=None,
        on_settings_write=None,
        on_pin_change=None,
        on_reboot=None,
        on_show_passkey=None,
        on_pairing_complete=None,
        device_info_characteristic=None,
    ):
        self._auth_manager = auth_manager
        self._on_show_passkey = on_show_passkey
        self._on_pairing_complete = on_pairing_complete
        self._device_info_characteristic = device_info_characteristic
        self._running = False
        self._discoverable = False
        self._timeout_s = PAIRING_MODE_TIMEOUT_SECONDS
        self._companion_connected = False

    def start(self) -> None:
        self._running = True
        logging.info("[BLE][MOCK] start")

    def stop(self) -> None:
        self._running = False
        logging.info("[BLE][MOCK] stop")

    def set_discoverable(self, enabled: bool, timeout_s: int = PAIRING_MODE_TIMEOUT_SECONDS) -> None:
        self._discoverable = bool(enabled)
        self._timeout_s = int(timeout_s)
        logging.info("[BLE][MOCK] set_discoverable enabled=%s timeout=%s", enabled, timeout_s)

    def notify_device_status(self, status: dict) -> None:
        logging.info("[BLE][MOCK] notify_device_status %s", status)

    def notify_notification_relay(self, notif: dict) -> None:
        logging.info("[BLE][MOCK] notify_notification_relay %s", notif)

    def is_companion_connected(self) -> bool:
        return self._companion_connected

    def get_device_address(self) -> str:
        return "mock-BT-addr"


def get_gatt_server(**kwargs) -> BitosGATTServer | MockGATTServer:
    if _BLUEZ_AVAILABLE and os.environ.get("BITOS_BLUETOOTH") != "mock":
        return BitosGATTServer(**kwargs)
    return MockGATTServer(**kwargs)
