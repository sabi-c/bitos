import json
import time
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from bluetooth.characteristics.device_status import DeviceStatusCharacteristic


class DeviceStatusCharacteristicTests(unittest.TestCase):
    def test_readvalue_returns_valid_json(self):
        ch = DeviceStatusCharacteristic()
        data = json.loads(ch.ReadValue({}).decode())
        self.assertIn("active_screen", data)

    def test_update_and_notify_updates_state(self):
        ch = DeviceStatusCharacteristic()
        ch.update_and_notify({"active_screen": "chat", "ai_online": True})
        data = json.loads(ch.ReadValue({}).decode())
        self.assertEqual(data["active_screen"], "chat")
        self.assertTrue(data["ai_online"])

    def test_periodic_update_thread_start_stop(self):
        ch = DeviceStatusCharacteristic()
        calls = {"n": 0}

        def get_status():
            calls["n"] += 1
            return {"uptime_seconds": calls["n"]}

        ch.start_periodic_updates(get_status, interval_s=1)
        time.sleep(1.2)
        ch.stop_periodic_updates()
        self.assertGreaterEqual(calls["n"], 1)


if __name__ == "__main__":
    unittest.main()
