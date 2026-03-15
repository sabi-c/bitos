import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from hardware.system_monitor import SystemMonitor


class SystemMonitorTests(unittest.TestCase):
    def test_get_snapshot_contains_expected_keys(self):
        monitor = SystemMonitor(interval=30)
        snapshot = monitor.get_snapshot()
        expected = {
            "cpu_percent",
            "ram_used_mb",
            "ram_total_mb",
            "ram_percent",
            "temp_c",
            "disk_percent",
        }
        self.assertTrue(expected.issubset(snapshot.keys()))


if __name__ == "__main__":
    unittest.main()
