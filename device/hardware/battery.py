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
        self._pisugar = None

    def get_status(self) -> dict:
        if time.time() - self._last_read < self._cache_ttl:
            return {"pct": self._pct, "charging": self._charging}
        self._refresh()
        return {"pct": self._pct, "charging": self._charging}

    def _refresh(self):
        self._last_read = time.time()
        if os.environ.get("BITOS_BATTERY") == "mock":
            return

        if self._read_with_pisugar():
            return
        self._read_with_smbus2()

    def _read_with_pisugar(self) -> bool:
        try:
            if self._pisugar is None:
                import pisugar  # type: ignore

                self._pisugar = pisugar.PiSugar()

            pct = getattr(self._pisugar, "get_battery_percentage", lambda: None)()
            charging = getattr(self._pisugar, "get_battery_charging", lambda: None)()
            if pct is None:
                return False
            self._pct = int(pct)
            if charging is not None:
                self._charging = bool(charging)
            return True
        except Exception:
            return False

    def _read_with_smbus2(self) -> None:
        try:
            import smbus2

            bus = smbus2.SMBus(1)
            self._pct = bus.read_byte_data(0x57, 0x2A)
            status = bus.read_byte_data(0x57, 0x02)
            self._charging = bool(status & 0x80)
        except Exception:
            pass
