import os
import secrets
import time

"""BITOS BLE UUIDs and authentication/pairing constants."""

# BITOS BLE Service UUIDs
# Base: B1705000-XXXX-4000-8000-000000000001

BITOS_SERVICE_UUID = "b1705000-0000-4000-8000-000000000001"
AUTH_CHALLENGE_UUID = "b1705000-0001-4000-8000-000000000001"
AUTH_RESPONSE_UUID = "b1705000-0002-4000-8000-000000000001"
WIFI_CONFIG_UUID = "b1705000-0010-4000-8000-000000000001"
WIFI_STATUS_UUID = "b1705000-0011-4000-8000-000000000001"
KEYBOARD_INPUT_UUID = "b1705000-0020-4000-8000-000000000001"
DEVICE_STATUS_UUID = "b1705000-0030-4000-8000-000000000001"
DEVICE_INFO_UUID = "b1705000-0099-4000-8000-000000000001"
NOTIFICATION_RELAY_UUID = "b1705000-0031-4000-8000-000000000001"
SETTINGS_READ_UUID = "b1705000-0040-4000-8000-000000000001"
SETTINGS_WRITE_UUID = "b1705000-0041-4000-8000-000000000001"
PIN_CHANGE_UUID = "b1705000-0050-4000-8000-000000000001"
REBOOT_CMD_UUID = "b1705000-0060-4000-8000-000000000001"

# Auth constants
SESSION_TOKEN_TTL_SECONDS = 300
MAX_AUTH_ATTEMPTS = 3
AUTH_LOCKOUT_SECONDS = 30
NONCE_TTL_SECONDS = 60
TIMESTAMP_TOLERANCE_SECONDS = 30

# Discoverable
PAIRING_MODE_TIMEOUT_SECONDS = 120

# Protected characteristics (require session token)
PROTECTED_CHARACTERISTICS = {
    WIFI_CONFIG_UUID,
    KEYBOARD_INPUT_UUID,
    SETTINGS_WRITE_UUID,
    PIN_CHANGE_UUID,
    REBOOT_CMD_UUID,
}


# Connectivity symbols
CONN_WIFI = "▣"
CONN_BT_PAN = "◈"
CONN_HOTSPOT = "▦"
CONN_OFFLINE = "✕"


COMPANION_BASE_URL = os.environ.get(
    "BITOS_COMPANION_URL",
    "https://bitos-p8xw.onrender.com",
)


def build_setup_url(ble_address: str) -> str:
    return f"{COMPANION_BASE_URL}/setup.html?ble={ble_address}&v=1"


def build_pair_url(ble_address: str) -> tuple[str, str, str, int]:
    """Build a pairing URL with ephemeral session token.

    Returns (url, session_id, token, expires) so the caller can register
    the pairing session with AuthManager.
    """
    session_id = secrets.token_urlsafe(16)
    token = secrets.token_urlsafe(24)
    expires = int(time.time()) + PAIRING_MODE_TIMEOUT_SECONDS
    url = (
        f"{COMPANION_BASE_URL}/pair.html"
        f"?ble={ble_address}&session={session_id}"
        f"&token={token}&exp={expires}&v=2"
    )
    return url, session_id, token, expires
