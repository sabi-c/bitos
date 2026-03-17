"""Bluetooth foundation package for BITOS companion connectivity."""

from .constants import (
    AUTH_CHALLENGE_UUID,
    AUTH_RESPONSE_UUID,
    BITOS_SERVICE_UUID,
    DEVICE_STATUS_UUID,
    DEVICE_INFO_UUID,
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
    "DEVICE_INFO_UUID",
    "NOTIFICATION_RELAY_UUID",
    "SETTINGS_READ_UUID",
    "SETTINGS_WRITE_UUID",
    "PIN_CHANGE_UUID",
    "REBOOT_CMD_UUID",
]

from .auth import AuthError, AuthManager
from .server import BitosGATTServer, MockGATTServer, get_gatt_server

__all__ += ["AuthError", "AuthManager", "BitosGATTServer", "MockGATTServer", "get_gatt_server"]

# Optional BT connection manager + AAP client — requires dbus-next / bluetooth sockets
from .bt_service import _DBUS_AVAILABLE as _HAS_DBUS  # noqa: F401
from .aap_client import _BT_AVAILABLE as _HAS_BLUETOOTH  # noqa: F401

try:
    from .bt_service import BTService, BTState, BTDeviceInfo, get_bt_service
    __all__ += ["BTService", "BTState", "BTDeviceInfo", "get_bt_service"]
except Exception:
    pass

try:
    from .aap_client import (
        AAPClient, AAPPressType, AAPBatteryStatus, AAPEarDetection,
        EarState, NoiseControlMode, press_type_name,
    )
    __all__ += [
        "AAPClient", "AAPPressType", "AAPBatteryStatus", "AAPEarDetection",
        "EarState", "NoiseControlMode", "press_type_name",
    ]
except Exception:
    pass

__all__ += ["_HAS_DBUS", "_HAS_BLUETOOTH"]
