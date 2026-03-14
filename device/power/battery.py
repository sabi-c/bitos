"""Battery monitor abstraction for context payloads."""

from device.storage.repository import DeviceRepository


class BatteryMonitor:
    """Read battery status from the local device repository."""

    def __init__(self, repository: DeviceRepository | None = None):
        self._repository = repository or DeviceRepository()

    def get_status(self) -> dict:
        pct_raw = self._repository.get_setting("battery_pct", 100)
        try:
            pct = int(pct_raw)
        except (TypeError, ValueError):
            pct = 100
        pct = max(0, min(100, pct))
        return {"pct": pct}
