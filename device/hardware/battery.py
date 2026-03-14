"""Battery monitoring via PiSugar with graceful fallbacks."""

from __future__ import annotations

import os
import time


class BatteryMonitor:
    """
    # WHY THIS EXISTS: reads PiSugar 3 battery via official library.
    # Falls back to raw smbus2 I2C if library unavailable.
    # Desktop mock: returns fixed 84%.
    """

    def __init__(self):
        self._pct = 84
        self._charging = False
        self._last_read = 0
        self._cache_ttl = 30

    def get_status(self) -> dict:
        if time.time() - self._last_read < self._cache_ttl:
            return {"pct": self._pct, "charging": self._charging}
        self._refresh()
        return {"pct": self._pct, "charging": self._charging}

    def _refresh(self):
        self._last_read = time.time()
        if os.environ.get("BITOS_BATTERY") == "mock":
            return

        try:
            from pisugar import PiSugarServer

            s = PiSugarServer()
            self._pct = int(s.get_battery_level())
            self._charging = bool(s.is_charging())
        except ImportError:
            import smbus2

            bus = smbus2.SMBus(1)
            self._pct = bus.read_byte_data(0x57, 0x2A)
            status = bus.read_byte_data(0x57, 0x02)
            self._charging = bool(status & 0x80)
        except Exception:
            pass
