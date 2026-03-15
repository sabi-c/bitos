"""Battery monitoring via PiSugar 3 (I2C bus 1, address 0x57)."""

from __future__ import annotations

import os
import time


class BatteryMonitor:
    I2C_BUS = 1
    I2C_ADDR = 0x57

    # Register defaults derived from the project PiSugar expectations.
    REG_PERCENT = 0x2A
    REG_STATUS = 0x02
    REG_VOLTAGE_MSB = 0x22
    REG_VOLTAGE_LSB = 0x23
    CHARGING_MASK = 0x80

    def __init__(self):
        self._pct = 84
        self._charging = False
        self._voltage_mv = 0
        self._last_read = 0.0
        self._cache_ttl = 30.0

    def get_status(self) -> dict:
        if time.time() - self._last_read >= self._cache_ttl:
            self._refresh()
        return {"pct": self._pct, "charging": self._charging}

    def _refresh(self):
        self._last_read = time.time()
        if os.environ.get("BITOS_BATTERY", "").lower() == "mock":
            return

        try:
            import smbus2

            bus = smbus2.SMBus(self.I2C_BUS)
            try:
                self._pct = self._read_percentage(bus)
                self._charging = self._read_charging(bus)
                if os.environ.get("BITOS_BATTERY_READ_VOLTAGE", "").lower() in {"1", "true", "yes"}:
                    self._voltage_mv = self._read_voltage_mv(bus)
            finally:
                close = getattr(bus, "close", None)
                if callable(close):
                    close()
        except Exception:
            pass

    def _read_percentage(self, bus) -> int:
        pct = int(bus.read_byte_data(self.I2C_ADDR, self.REG_PERCENT))
        if pct < 0:
            return 0
        if pct > 100:
            return 100
        return pct

    def _read_voltage_mv(self, bus) -> int:
        try:
            msb = int(bus.read_byte_data(self.I2C_ADDR, self.REG_VOLTAGE_MSB))
            lsb = int(bus.read_byte_data(self.I2C_ADDR, self.REG_VOLTAGE_LSB))
            return ((msb << 8) | lsb)
        except Exception:
            return 0

    def _read_charging(self, bus) -> bool:
        status = int(bus.read_byte_data(self.I2C_ADDR, self.REG_STATUS))
        return bool(status & self.CHARGING_MASK)


    def get_voltage_mv(self) -> int:
        """Return last sampled battery voltage in mV (0 when unavailable)."""
        return int(self._voltage_mv)
