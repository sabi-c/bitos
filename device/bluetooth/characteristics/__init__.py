"""Characteristic placeholders for BITOS BLE service."""

from .auth_challenge import AuthChallengeCharacteristic
from .auth_response import AuthResponseCharacteristic
from .device_status import DeviceStatusCharacteristic
from .device_info import DeviceInfoCharacteristic
from .keyboard_input import KeyboardInputCharacteristic
from .wifi_config import WiFiConfigCharacteristic, WiFiStatusCharacteristic

__all__ = [
    "AuthChallengeCharacteristic",
    "AuthResponseCharacteristic",
    "WiFiConfigCharacteristic",
    "WiFiStatusCharacteristic",
    "DeviceStatusCharacteristic",
    "DeviceInfoCharacteristic",
    "KeyboardInputCharacteristic",
]
