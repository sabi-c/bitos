"""Bluetooth foundation package for BITOS companion connectivity."""

from .constants import (
    AUTH_CHALLENGE_UUID,
    AUTH_RESPONSE_UUID,
    BITOS_SERVICE_UUID,
    DEVICE_STATUS_UUID,
    KEYBOARD_INPUT_UUID,
    NOTIFICATION_RELAY_UUID,
    PIN_CHANGE_UUID,
    REBOOT_CMD_UUID,
    SETTINGS_READ_UUID,
    SETTINGS_WRITE_UUID,
    WIFI_CONFIG_UUID,
    WIFI_STATUS_UUID,
)

__all__ = [
    "BITOS_SERVICE_UUID",
    "AUTH_CHALLENGE_UUID",
    "AUTH_RESPONSE_UUID",
    "WIFI_CONFIG_UUID",
    "WIFI_STATUS_UUID",
    "KEYBOARD_INPUT_UUID",
    "DEVICE_STATUS_UUID",
    "NOTIFICATION_RELAY_UUID",
    "SETTINGS_READ_UUID",
    "SETTINGS_WRITE_UUID",
    "PIN_CHANGE_UUID",
    "REBOOT_CMD_UUID",
]

from .auth import AuthError, AuthManager
from .server import BitosGATTServer, MockGATTServer, get_gatt_server

__all__ += ["AuthError", "AuthManager", "BitosGATTServer", "MockGATTServer", "get_gatt_server"]
