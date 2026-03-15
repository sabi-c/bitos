"""Battery monitoring via PiSugar 3 (I2C bus 1, address 0x57)."""

from __future__ import annotations

import importlib
import importlib.util
import os
import time


class BatteryMonitor:
    I2C_ADDR = 0x57
    I2C_BUS = 1
    REG_PERCENTAGE = 0x2A
    REG_VOLTAGE_H = 0x22
    REG_VOLTAGE_L = 0x23
    REG_STATUS = 0x02

    def __init__(self):
        self._status = {
            "pct": 84,
            "percentage": 84,
            "voltage": 0.0,
            "charging": False,
            "present": False,
        }
        self._last_read = 0.0
        self._cache_ttl = 30.0

    def get_status(self):
        if os.environ.get("BITOS_BATTERY", "").lower() == "mock":
            return {
                "pct": 84,
                "percentage": 84,
                "voltage": 0.0,
                "charging": False,
                "present": False,
            }

        if time.time() - self._last_read >= self._cache_ttl:
            self._status = self._refresh()
            self._last_read = time.time()
        return dict(self._status)

    def _refresh(self) -> dict:
        if importlib.util.find_spec("smbus2") is None:
            return {
                "pct": 0,
                "percentage": 0,
                "voltage": 0.0,
                "charging": False,
                "present": False,
                "error": "No module named 'smbus2'",
            }

        smbus2 = importlib.import_module("smbus2")

        try:
            bus = smbus2.SMBus(self.I2C_BUS)
            try:
                pct = bus.read_byte_data(self.I2C_ADDR, self.REG_PERCENTAGE)
                vh = bus.read_byte_data(self.I2C_ADDR, self.REG_VOLTAGE_H)
                vl = bus.read_byte_data(self.I2C_ADDR, self.REG_VOLTAGE_L)
                status = bus.read_byte_data(self.I2C_ADDR, self.REG_STATUS)
            finally:
                bus.close()

            voltage = (((vh & 0x3F) << 8) | vl) / 1000.0
            charging = bool(status & 0x80)
            percentage = int(max(0, min(100, pct)))
            return {
                "pct": percentage,
                "percentage": percentage,
                "voltage": voltage,
                "charging": charging,
                "present": True,
            }
        except Exception as e:
            return {
                "pct": 0,
                "percentage": 0,
                "voltage": 0.0,
                "charging": False,
                "present": False,
                "error": str(e),
            }
