import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from hardware.led import LEDController


class LEDControllerTests(unittest.TestCase):
    def test_instantiates_and_methods_exist(self):
        led = LEDController()
        self.assertIsNotNone(led)
        for method in ("set_color", "off", "thinking", "listening", "speaking", "error"):
            self.assertTrue(hasattr(led, method))


if __name__ == "__main__":
    unittest.main()
