import unittest
from pathlib import Path


class CompanionProtocolDocTests(unittest.TestCase):
    def test_companion_protocol_exists_with_required_sections(self):
        path = Path("device/bluetooth/COMPANION_PROTOCOL.md")
        self.assertTrue(path.exists())
        text = path.read_text()
        for header in [
            "# BITOS BLE Companion Protocol",
            "## Connection flow",
            "## WiFi provisioning",
            "## Keyboard input",
            "## Device status monitoring",
        ]:
            self.assertIn(header, text)


if __name__ == "__main__":
    unittest.main()
