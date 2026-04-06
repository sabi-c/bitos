"""Tests for BluetoothAudioPanel state management.

Tests the BTService state integration without requiring pygame
(which is only available on the device).  We pre-populate sys.modules
with stubs for all display/pygame/screens dependencies so the panel
module can be imported cleanly.
"""
import os
import sys
import types
import unittest
from unittest.mock import MagicMock
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

# ------------------------------------------------------------------
# Stub out pygame and all device UI modules before any imports
# ------------------------------------------------------------------
_DEVICE_DIR = str(Path(__file__).resolve().parents[1] / "device")

_STUB_MODULES = [
    "pygame", "pygame.event", "pygame.draw", "pygame.font",
    "display", "display.driver", "display.theme", "display.tokens",
    "screens", "screens.base", "screens.components",
]

for _name in _STUB_MODULES:
    if _name not in sys.modules:
        mod = types.ModuleType(_name)
        # Give package stubs a __path__ so sub-imports work
        if "." not in _name:
            mod.__path__ = [os.path.join(_DEVICE_DIR, _name)]
        sys.modules[_name] = mod

# screens.panels needs a real __path__ so bt_audio can be found
if "screens.panels" not in sys.modules:
    _panels = types.ModuleType("screens.panels")
    _panels.__path__ = [os.path.join(_DEVICE_DIR, "screens", "panels")]
    sys.modules["screens.panels"] = _panels

# Pygame constants the panel references
_pg = sys.modules["pygame"]
_pg.Surface = MagicMock
_pg.Rect = MagicMock
_pg.draw = MagicMock()
_pg.KEYDOWN = 768
_pg.K_DOWN = 274
_pg.K_UP = 273
_pg.K_RETURN = 13
_pg.K_SPACE = 32
_pg.K_ESCAPE = 27
_pg.K_j = 106
_pg.K_k = 107

# display.theme stubs
sys.modules["display.theme"].load_ui_font = MagicMock(return_value=MagicMock())
sys.modules["display.theme"].merge_runtime_ui_settings = MagicMock(return_value={})

# display.tokens stubs
_tok = sys.modules["display.tokens"]
_tok.BLACK = (0, 0, 0)
_tok.WHITE = (255, 255, 255)
_tok.DIM2 = (80, 80, 80)
_tok.DIM3 = (50, 50, 50)
_tok.HAIRLINE = (30, 30, 30)
_tok.PHYSICAL_W = 240
_tok.PHYSICAL_H = 240
_tok.STATUS_BAR_H = 20
_tok.ROW_H_MIN = 24

# screens stubs
sys.modules["screens.base"].BaseScreen = object
sys.modules["screens.components"].NavItem = MagicMock
sys.modules["screens.components"].VerticalNavController = MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from bluetooth.bt_service import BTState


class TestBTAudioPanelState(unittest.TestCase):

    def _make_panel(self, bt_state=None, connected_name=None):
        from screens.panels.bt_audio import BluetoothAudioPanel

        mock_bt = MagicMock()
        mock_bt.get_connected_device.return_value = None

        mock_service = MagicMock()
        mock_service.state = bt_state or BTState.DISCONNECTED
        if connected_name:
            mock_dev = MagicMock()
            mock_dev.name = connected_name
            mock_dev.to_dict.return_value = {"name": connected_name, "address": "AA:BB:CC:DD:EE:FF"}
            mock_service.connected_device = mock_dev
        else:
            mock_service.connected_device = None

        return BluetoothAudioPanel(
            bt_audio_manager=mock_bt,
            bt_service=mock_service,
        )

    def test_panel_accepts_bt_service(self):
        panel = self._make_panel()
        self.assertIsNotNone(panel._bt_service)

    def test_status_disconnected(self):
        panel = self._make_panel()
        status = panel._get_connection_status_text()
        self.assertIn("NO DEVICE", status)

    def test_status_connected(self):
        panel = self._make_panel(bt_state=BTState.CONNECTED, connected_name="Seb's AirPods")
        panel._bt_state = BTState.CONNECTED
        panel._connected_device_name = "Seb's AirPods"
        status = panel._get_connection_status_text()
        self.assertIn("AirPods", status)

    def test_status_reconnecting(self):
        panel = self._make_panel(bt_state=BTState.CONNECTING)
        panel._bt_state = BTState.CONNECTING
        panel._reconnect_attempt = 3
        status = panel._get_connection_status_text()
        self.assertIn("RECONNECTING", status)

    def test_status_playing(self):
        panel = self._make_panel(bt_state=BTState.PLAYING, connected_name="JBL Speaker")
        panel._bt_state = BTState.PLAYING
        panel._connected_device_name = "JBL Speaker"
        status = panel._get_connection_status_text()
        self.assertIn("JBL Speaker", status)

    def test_update_picks_up_new_connection(self):
        """update() should detect when BTService connects a device."""
        panel = self._make_panel()
        mock_dev = MagicMock()
        mock_dev.name = "AirPods Pro"
        mock_dev.to_dict.return_value = {"name": "AirPods Pro", "address": "11:22:33:44:55:66"}
        panel._bt_service.state = BTState.CONNECTED
        panel._bt_service.connected_device = mock_dev

        panel.update(0.016)

        self.assertEqual(panel._bt_state, BTState.CONNECTED)
        self.assertEqual(panel._connected_device_name, "AirPods Pro")
        self.assertIsNotNone(panel._connected_device)

    def test_update_picks_up_disconnection(self):
        """update() should detect when BTService loses connection."""
        panel = self._make_panel(bt_state=BTState.CONNECTED, connected_name="AirPods Pro")
        panel._bt_state = BTState.CONNECTED
        panel._connected_device = {"name": "AirPods Pro", "address": "11:22:33:44:55:66"}
        panel._connected_device_name = "AirPods Pro"

        panel._bt_service.state = BTState.DISCONNECTED
        panel._bt_service.connected_device = None

        panel.update(0.016)

        self.assertEqual(panel._bt_state, BTState.DISCONNECTED)
        self.assertIsNone(panel._connected_device)
        self.assertEqual(panel._connected_device_name, "")


if __name__ == "__main__":
    unittest.main()
