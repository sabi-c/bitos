"""WiFi config and status characteristics."""
from __future__ import annotations

import json
import os
from typing import Callable

from bluetooth.auth import AuthError, AuthManager
from bluetooth.crypto import decrypt_wifi_password


class WiFiStatusCharacteristic:
    """Read/notify characteristic payload surface for WiFi status."""

    def __init__(self):
        self._status = {
            "connected": False,
            "ssid": "",
            "signal": "weak",
            "ip": "",
            "last_error": None,
        }

    def ReadValue(self, _options) -> bytes:
        return json.dumps(self._status).encode("utf-8")

    def update(self, status: dict) -> None:
        merged = dict(self._status)
        merged.update(status)
        self._status = merged


class WiFiConfigCharacteristic:
    """Protected WiFi provisioning write characteristic."""

    def __init__(self, auth_manager: AuthManager, on_wifi_config: Callable, wifi_status: WiFiStatusCharacteristic | None = None):
        self._auth_manager = auth_manager
        self._on_wifi_config = on_wifi_config
        self._wifi_status = wifi_status or WiFiStatusCharacteristic()

    def WriteValue(self, value, _options):
        raw = bytes(value)
        payload = json.loads(raw.decode("utf-8"))

        session_token = str(payload.get("session_token", ""))
        if not self._auth_manager.validate_session_token(session_token):
            raise AuthError("INVALID_SESSION_TOKEN")

        ssid = str(payload.get("ssid", "")).strip()
        encrypted_password = str(payload.get("password", ""))
        security = str(payload.get("security", "WPA2")).upper()
        priority = int(payload.get("priority", 100))
        if not ssid:
            raise ValueError("SSID_REQUIRED")

        if security == "OPEN":
            password = ""
        else:
            ble_secret = os.environ.get("BITOS_BLE_SECRET", "")
            password = decrypt_wifi_password(encrypted_password, session_token=session_token, ble_secret_hex=ble_secret)

        ok = bool(self._on_wifi_config(ssid, password, security, priority))
        self._wifi_status.update(
            {
                "connected": ok,
                "ssid": ssid,
                "signal": "good" if ok else "weak",
                "last_error": None if ok else "apply_failed",
            }
        )
