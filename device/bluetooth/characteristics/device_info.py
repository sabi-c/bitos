"""Read-only device metadata characteristic."""
from __future__ import annotations

import json

from bluetooth.constants import COMPANION_BASE_URL


def _read_pi_serial() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("Serial"):
                    return line.split(":")[1].strip()
    except Exception:
        pass
    return "DESKTOP-DEV-001"


class DeviceInfoCharacteristic:
    """
    # WHY THIS EXISTS: allows companion app to read device serial
    # for BLE secret derivation without embedding it in QR URL params.
    # No auth required — serial is not sensitive.
    """

    def ReadValue(self, options) -> bytes:
        _ = options
        return json.dumps(
            {
                "serial": _read_pi_serial(),
                "version": "1.0.0",
                "model": "BITOS-1",
                "ble_protocol_version": 1,
                "companion_url": COMPANION_BASE_URL,
            }
        ).encode()
