"""BlueZ GATT server for BITOS companion app connectivity.

Real implementation uses bluezero to register the BITOS GATT service
with all characteristics.  MockGATTServer provides a no-op fallback
for desktop dev and tests.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

from .constants import (
    AUTH_CHALLENGE_UUID,
    AUTH_RESPONSE_UUID,
    BITOS_SERVICE_UUID,
    DEVICE_INFO_UUID,
    DEVICE_STATUS_UUID,
    KEYBOARD_INPUT_UUID,
    PAIRING_MODE_TIMEOUT_SECONDS,
    WIFI_CONFIG_UUID,
    WIFI_STATUS_UUID,
)

logger = logging.getLogger(__name__)

# Retry configuration — mirrors NUS service
_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 5


class BitosGATTServer:
    """BlueZ-backed GATT server that registers the BITOS service and all
    characteristics via bluezero so the companion app can discover and
    interact with them over Web Bluetooth.
    """

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
        self._healthy = False
        self._thread: threading.Thread | None = None
        self._peripheral = None
        self._discoverable = False
        self._pairing_until = 0.0
        self._companion_connected = False
        self._stop_event = threading.Event()

        # Internal state for auth response read-back
        self._last_auth_result: bytes = b""
        self._last_auth_lock = threading.Lock()

        # Lazy-created characteristic helpers
        self._wifi_status_char = None
        self._wifi_config_char = None
        self._device_status_char = None
        self._keyboard_input_char = None

        # Reference to the bluezero device status characteristic for notify
        self._bz_device_status_char = None

    # ------------------------------------------------------------------
    # Public API (unchanged interface)
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="bitos-gatt", daemon=True)
        self._thread.start()
        logger.info("[BLE] GATT server starting")

    def stop(self) -> None:
        self._running = False
        self._healthy = False
        self._stop_event.set()
        if self._peripheral:
            try:
                self._peripheral.stop_advertising()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("[BLE] GATT server stopped")

    def set_discoverable(self, enabled: bool, timeout_s: int = PAIRING_MODE_TIMEOUT_SECONDS) -> None:
        self._discoverable = bool(enabled)
        if enabled:
            self._pairing_until = time.time() + max(1, int(timeout_s))
        else:
            self._pairing_until = 0.0

    def notify_device_status(self, status: dict) -> None:
        """Push a device status update to connected companion via notify."""
        if self._device_status_char is not None:
            self._device_status_char.update_and_notify(status)
        if self._bz_device_status_char is not None:
            try:
                payload = json.dumps(status).encode("utf-8")
                self._bz_device_status_char.set_value(list(payload))
            except Exception as exc:
                logger.debug("[BLE] notify device status error: %s", exc)

    def notify_notification_relay(self, notif: dict) -> None:
        logger.info("[BLE] relay notification: %s", notif)

    def is_companion_connected(self) -> bool:
        return self._companion_connected

    def get_device_address(self) -> str:
        if self._peripheral is not None:
            try:
                return self._peripheral.address
            except Exception:
                pass
        return os.environ.get("BITOS_BLE_ADDRESS", "AA:BB:CC:DD:EE:FF")

    # ------------------------------------------------------------------
    # Thread entry — retry loop (same pattern as NUS service)
    # ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            from bluezero import adapter, peripheral  # type: ignore
        except ImportError:
            logger.warning("[BLE] bluezero not installed — GATT server disabled")
            self._running = False
            return

        retries = 0
        while self._running and retries < _MAX_RETRIES:
            try:
                self._setup_peripheral(adapter, peripheral)
                self._healthy = True
                logger.info("[BLE] GATT peripheral published and advertising")
                return  # publish() blocks until stopped
            except Exception as exc:
                retries += 1
                self._healthy = False
                self._companion_connected = False
                logger.error(
                    "[BLE] GATT setup failed (attempt %d/%d): %s",
                    retries, _MAX_RETRIES, exc,
                )
                if retries < _MAX_RETRIES and self._running:
                    time.sleep(_RETRY_DELAY_SECONDS)

        if self._running:
            logger.error("[BLE] GATT server gave up after %d retries — running degraded", _MAX_RETRIES)
        self._running = False

    # ------------------------------------------------------------------
    # Peripheral setup — registers the BITOS service + all characteristics
    # ------------------------------------------------------------------

    def _setup_peripheral(self, adapter_mod, peripheral_mod) -> None:
        """Create the bluezero peripheral with the full BITOS GATT service."""
        adapters = adapter_mod.list_adapters()
        if not adapters:
            raise RuntimeError("No Bluetooth adapter found")

        addr = adapters[0]
        dongle = adapter_mod.Adapter(addr)
        dongle.powered = True

        self._peripheral = peripheral_mod.Peripheral(addr, local_name="BITOS")

        # -- Service --
        srv_id = 1
        self._peripheral.add_service(srv_id=srv_id, uuid=BITOS_SERVICE_UUID, primary=True)

        # -- Lazy-create characteristic helpers --
        self._init_characteristic_helpers()

        # chr_id numbering: 1-based, sequential within the service
        chr_id = 0

        # 1. AUTH_CHALLENGE — READ
        chr_id += 1
        self._peripheral.add_characteristic(
            srv_id=srv_id,
            chr_id=chr_id,
            uuid=AUTH_CHALLENGE_UUID,
            value=[],
            notifying=False,
            flags=["read"],
            read_callback=self._read_auth_challenge,
            write_callback=None,
            notify_callback=None,
        )

        # 2. AUTH_RESPONSE — WRITE + READ
        chr_id += 1
        self._peripheral.add_characteristic(
            srv_id=srv_id,
            chr_id=chr_id,
            uuid=AUTH_RESPONSE_UUID,
            value=[],
            notifying=False,
            flags=["read", "write"],
            read_callback=self._read_auth_response,
            write_callback=self._write_auth_response,
            notify_callback=None,
        )

        # 3. WIFI_CONFIG — WRITE (write-without-response for companion compat)
        chr_id += 1
        self._peripheral.add_characteristic(
            srv_id=srv_id,
            chr_id=chr_id,
            uuid=WIFI_CONFIG_UUID,
            value=[],
            notifying=False,
            flags=["write", "write-without-response"],
            read_callback=None,
            write_callback=self._write_wifi_config,
            notify_callback=None,
        )

        # 4. WIFI_STATUS — READ
        chr_id += 1
        self._peripheral.add_characteristic(
            srv_id=srv_id,
            chr_id=chr_id,
            uuid=WIFI_STATUS_UUID,
            value=[],
            notifying=False,
            flags=["read"],
            read_callback=self._read_wifi_status,
            write_callback=None,
            notify_callback=None,
        )

        # 5. KEYBOARD_INPUT — WRITE
        chr_id += 1
        self._peripheral.add_characteristic(
            srv_id=srv_id,
            chr_id=chr_id,
            uuid=KEYBOARD_INPUT_UUID,
            value=[],
            notifying=False,
            flags=["write", "write-without-response"],
            read_callback=None,
            write_callback=self._write_keyboard_input,
            notify_callback=None,
        )

        # 6. DEVICE_STATUS — READ + NOTIFY
        chr_id += 1
        self._peripheral.add_characteristic(
            srv_id=srv_id,
            chr_id=chr_id,
            uuid=DEVICE_STATUS_UUID,
            value=[],
            notifying=False,
            flags=["read", "notify"],
            read_callback=self._read_device_status,
            write_callback=None,
            notify_callback=self._on_device_status_notify,
        )

        # 7. DEVICE_INFO — READ
        chr_id += 1
        self._peripheral.add_characteristic(
            srv_id=srv_id,
            chr_id=chr_id,
            uuid=DEVICE_INFO_UUID,
            value=[],
            notifying=False,
            flags=["read"],
            read_callback=self._read_device_info,
            write_callback=None,
            notify_callback=None,
        )

        # Grab reference for notify pushes (DEVICE_STATUS is chr_id 6)
        try:
            self._bz_device_status_char = self._peripheral.services[srv_id].characteristics[6]
        except (KeyError, IndexError, AttributeError):
            logger.debug("[BLE] Could not grab device status char reference for notify")

        # Connection callbacks
        self._peripheral.on_connect = self._on_companion_connect
        self._peripheral.on_disconnect = self._on_companion_disconnect

        # publish() blocks — runs the GLib main loop
        self._peripheral.publish()

    # ------------------------------------------------------------------
    # Characteristic helper initialization
    # ------------------------------------------------------------------

    def _init_characteristic_helpers(self) -> None:
        """Create the characteristic handler objects that hold state."""
        from .characteristics.wifi_config import WiFiConfigCharacteristic, WiFiStatusCharacteristic
        from .characteristics.device_status import DeviceStatusCharacteristic
        from .characteristics.keyboard_input import KeyboardInputCharacteristic

        self._wifi_status_char = WiFiStatusCharacteristic()

        if self._on_wifi_config is not None:
            self._wifi_config_char = WiFiConfigCharacteristic(
                auth_manager=self._auth_manager,
                on_wifi_config=self._on_wifi_config,
                wifi_status=self._wifi_status_char,
            )

        self._device_status_char = DeviceStatusCharacteristic()

        if self._on_keyboard_input is not None:
            self._keyboard_input_char = KeyboardInputCharacteristic(
                auth_manager=self._auth_manager,
                on_keyboard_input=self._on_keyboard_input,
            )

    # ------------------------------------------------------------------
    # Characteristic callbacks — bridge bluezero ↔ characteristic classes
    # ------------------------------------------------------------------

    def _read_auth_challenge(self) -> list[int]:
        """AUTH_CHALLENGE read: return JSON {nonce, timestamp}."""
        try:
            challenge = self._auth_manager.get_challenge()
            payload = json.dumps(challenge).encode("utf-8")
            return list(payload)
        except Exception as exc:
            logger.error("[BLE] auth challenge read error: %s", exc)
            return list(json.dumps({"error": str(exc)}).encode("utf-8"))

    def _write_auth_response(self, value, options=None) -> None:
        """AUTH_RESPONSE write: accept HMAC auth, store result for read-back."""
        del options
        try:
            raw = bytes(value)
            payload = json.loads(raw.decode("utf-8"))

            nonce = str(payload.get("nonce", ""))
            response_hex = str(payload.get("response", ""))
            pairing_session = payload.get("pairing_session")
            pairing_token = payload.get("pairing_token")

            # Use a generic client address — BlueZ doesn't expose remote addr
            # in the characteristic write callback easily.
            client_addr = "ble-companion"

            token = self._auth_manager.verify_response(
                client_addr=client_addr,
                nonce=nonce,
                response_hex=response_hex,
                pairing_session_id=pairing_session,
                pairing_token=pairing_token,
            )
            result = json.dumps({"session_token": token}).encode("utf-8")

            if self._on_pairing_complete is not None:
                try:
                    self._on_pairing_complete()
                except Exception as exc:
                    logger.error("[BLE] on_pairing_complete callback error: %s", exc)

        except Exception as exc:
            error_msg = str(exc)
            logger.warning("[BLE] auth response rejected: %s", error_msg)
            result = json.dumps({"error": error_msg}).encode("utf-8")

        with self._last_auth_lock:
            self._last_auth_result = result

    def _read_auth_response(self) -> list[int]:
        """AUTH_RESPONSE read: return the result of the last write (session_token or error)."""
        with self._last_auth_lock:
            data = self._last_auth_result
        if not data:
            return list(json.dumps({"error": "NO_AUTH_ATTEMPT"}).encode("utf-8"))
        return list(data)

    def _write_wifi_config(self, value, options=None) -> None:
        """WIFI_CONFIG write: delegate to WiFiConfigCharacteristic."""
        del options
        try:
            if self._wifi_config_char is not None:
                self._wifi_config_char.WriteValue(value, None)
            else:
                logger.warning("[BLE] WiFi config write but no handler configured")
        except Exception as exc:
            logger.error("[BLE] WiFi config write error: %s", exc)

    def _read_wifi_status(self) -> list[int]:
        """WIFI_STATUS read: return current WiFi status JSON."""
        try:
            if self._wifi_status_char is not None:
                payload = self._wifi_status_char.ReadValue(None)
                return list(payload)
        except Exception as exc:
            logger.error("[BLE] WiFi status read error: %s", exc)
        return list(json.dumps({"connected": False, "ssid": "", "signal": "weak", "ip": "", "last_error": None}).encode("utf-8"))

    def _write_keyboard_input(self, value, options=None) -> None:
        """KEYBOARD_INPUT write: delegate to KeyboardInputCharacteristic."""
        del options
        try:
            if self._keyboard_input_char is not None:
                self._keyboard_input_char.WriteValue(value, None)
            else:
                logger.warning("[BLE] Keyboard input write but no handler configured")
        except Exception as exc:
            logger.error("[BLE] Keyboard input write error: %s", exc)

    def _read_device_status(self) -> list[int]:
        """DEVICE_STATUS read: return current device status JSON."""
        try:
            if self._device_status_char is not None:
                payload = self._device_status_char.ReadValue(None)
                return list(payload)
        except Exception as exc:
            logger.error("[BLE] Device status read error: %s", exc)
        return list(json.dumps({}).encode("utf-8"))

    def _on_device_status_notify(self, notifying, characteristic) -> None:
        """Called when companion subscribes/unsubscribes to device status notifications."""
        del characteristic
        logger.debug("[BLE] Device status notify: %s", notifying)

    def _read_device_info(self) -> list[int]:
        """DEVICE_INFO read: return device metadata JSON."""
        try:
            if self._device_info_characteristic is not None:
                payload = self._device_info_characteristic.ReadValue(None)
                return list(payload)
        except Exception as exc:
            logger.error("[BLE] Device info read error: %s", exc)
        return list(json.dumps({"serial": "UNKNOWN", "model": "BITOS-1", "ble_protocol_version": 1}).encode("utf-8"))

    # ------------------------------------------------------------------
    # Connection callbacks
    # ------------------------------------------------------------------

    def _on_companion_connect(self, device) -> None:
        self._companion_connected = True
        logger.info("[BLE] Companion connected: %s", device)
        if self._on_pairing_complete is not None:
            # Note: pairing_complete fires on auth success, not raw connect
            pass

    def _on_companion_disconnect(self, device) -> None:
        self._companion_connected = False
        logger.info("[BLE] Companion disconnected: %s", device)
        # Clear auth state on disconnect
        with self._last_auth_lock:
            self._last_auth_result = b""


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
    try:
        import bluezero  # noqa: F401
        _bluez_available = True
    except ImportError:
        _bluez_available = False

    if _bluez_available and os.environ.get("BITOS_BLUETOOTH") != "mock":
        return BitosGATTServer(**kwargs)
    return MockGATTServer(**kwargs)
