from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from hardware.battery import BatteryMonitor


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def time(self) -> float:
        return self.now


def test_battery_monitor_mock_status(monkeypatch):
    monkeypatch.setenv("BITOS_BATTERY", "mock")
    clock = FakeClock()
    monkeypatch.setattr("hardware.battery.time", clock)

    monitor = BatteryMonitor()
    status = monitor.get_status()

    assert set(status) == {"pct", "charging"}
    assert status["pct"] == 84
    assert status["charging"] is False


def test_battery_monitor_cache_within_ttl_skips_i2c(monkeypatch):
    monkeypatch.delenv("BITOS_BATTERY", raising=False)
    clock = FakeClock()
    monkeypatch.setattr("hardware.battery.time", clock)

    calls = {"count": 0}

    class FakeBus:
        def __init__(self, _bus_num):
            pass

        def read_byte_data(self, _addr, register):
            calls["count"] += 1
            if register == 0x2A:
                return 91
            if register == 0x02:
                return 0x80
            return 0

    monkeypatch.setitem(sys.modules, "pisugar", SimpleNamespace(PiSugar=lambda: (_ for _ in ()).throw(RuntimeError("no lib"))))
    monkeypatch.setitem(sys.modules, "smbus2", SimpleNamespace(SMBus=FakeBus))

    monitor = BatteryMonitor()
    first = monitor.get_status()
    second = monitor.get_status()

    assert first == second == {"pct": 91, "charging": True}
    assert calls["count"] == 2


def test_battery_monitor_cache_expires_triggers_refresh(monkeypatch):
    monkeypatch.delenv("BITOS_BATTERY", raising=False)
    clock = FakeClock()
    monkeypatch.setattr("hardware.battery.time", clock)

    calls = {"count": 0}

    class FakeBus:
        def __init__(self, _bus_num):
            pass

        def read_byte_data(self, _addr, register):
            calls["count"] += 1
            if register == 0x2A:
                return 62
            if register == 0x02:
                return 0
            return 0

    monkeypatch.setitem(sys.modules, "pisugar", SimpleNamespace(PiSugar=lambda: (_ for _ in ()).throw(RuntimeError("no lib"))))
    monkeypatch.setitem(sys.modules, "smbus2", SimpleNamespace(SMBus=FakeBus))

    monitor = BatteryMonitor()
    _ = monitor.get_status()
    clock.now += 31
    refreshed = monitor.get_status()

    assert refreshed == {"pct": 62, "charging": False}
    assert calls["count"] == 4
