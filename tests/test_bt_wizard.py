"""Tests for Bluetooth pairing wizard screen."""
import os
import sys
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import pygame
pygame.init()


def _make_mock_bt_service(is_available=True, connected_device=None):
    """Create a mock BTService for testing."""
    svc = MagicMock()
    svc.is_available = is_available
    svc.connected_device = connected_device
    svc.known_devices = {}
    svc.discover = AsyncMock(return_value=[])
    svc.pair_and_connect = AsyncMock(return_value=True)
    svc.forget = AsyncMock(return_value=True)
    return svc


def _make_mock_device(name="Test Device", address="AA:BB:CC:DD:EE:FF", rssi=-42, is_audio=True, is_airpods=False):
    """Create a mock BTDeviceInfo."""
    dev = MagicMock()
    dev.name = name
    dev.address = address
    dev.rssi = rssi
    dev.is_audio = is_audio
    dev.is_airpods = is_airpods
    dev.paired = False
    dev.to_dict.return_value = {
        "name": name,
        "address": address,
        "rssi": rssi,
        "is_audio": is_audio,
        "is_airpods": is_airpods,
    }
    return dev


class TestBTWizardInit(unittest.TestCase):
    """Tests for BTWizardScreen initialization."""

    def test_initial_state(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        self.assertEqual(wizard._state, WizardState.MENU)
        self.assertEqual(wizard._found_devices, [])
        self.assertIsNone(wizard._selected_device)

    def test_init_with_bt_service(self):
        from screens.bt_wizard import BTWizardScreen
        svc = _make_mock_bt_service()
        wizard = BTWizardScreen(bt_service=svc)
        self.assertEqual(wizard._bt, svc)

    def test_screen_name(self):
        from screens.bt_wizard import BTWizardScreen
        wizard = BTWizardScreen()
        self.assertEqual(wizard.SCREEN_NAME, "BT_WIZARD")


class TestBTWizardNavigation(unittest.TestCase):
    """Tests for wizard state transitions via button events."""

    def test_menu_short_press_moves_nav(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        wizard._state = WizardState.MENU

        initial_focus = wizard._menu_nav.focus_index
        wizard.handle_action("SHORT_PRESS")
        self.assertEqual(wizard._menu_nav.focus_index, initial_focus + 1)

    def test_menu_triple_press_moves_up(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        wizard._state = WizardState.MENU

        # Move down first
        wizard.handle_action("SHORT_PRESS")
        wizard.handle_action("TRIPLE_PRESS")
        self.assertEqual(wizard._menu_nav.focus_index, 0)

    def test_long_press_on_menu_goes_back(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        back_called = []
        wizard = BTWizardScreen(on_back=lambda: back_called.append(True))
        wizard._state = WizardState.MENU

        wizard.handle_action("LONG_PRESS")
        self.assertEqual(len(back_called), 1)

    def test_long_press_on_scanning_cancels(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        wizard._state = WizardState.SCANNING
        wizard._scan_task = MagicMock()
        wizard._scan_task.done.return_value = False

        wizard.handle_action("LONG_PRESS")
        self.assertEqual(wizard._state, WizardState.MENU)
        wizard._scan_task.cancel.assert_called_once()

    def test_long_press_on_pairing_goes_back(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        wizard._state = WizardState.PAIRING

        wizard.handle_action("LONG_PRESS")
        self.assertEqual(wizard._state, WizardState.MENU)

    def test_double_press_on_failed_retries(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        mock_device = _make_mock_device()
        svc = _make_mock_bt_service()
        wizard = BTWizardScreen(bt_service=svc)
        wizard._state = WizardState.FAILED
        wizard._selected_device = mock_device

        wizard.handle_action("DOUBLE_PRESS")
        self.assertEqual(wizard._state, WizardState.PAIRING)

    def test_long_press_on_failed_goes_back(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        wizard._state = WizardState.FAILED

        wizard.handle_action("LONG_PRESS")
        self.assertEqual(wizard._state, WizardState.MENU)

    def test_long_press_on_connected_finishes(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        back_called = []
        wizard = BTWizardScreen(on_back=lambda: back_called.append(True))
        wizard._state = WizardState.CONNECTED
        wizard._connected_nav = wizard._build_connected_nav()

        wizard.handle_action("LONG_PRESS")
        self.assertEqual(len(back_called), 1)


class TestBTWizardHandleEvent(unittest.TestCase):
    """Tests for handle_event (ButtonEvent dispatch)."""

    def test_handle_event_maps_correctly(self):
        from screens.bt_wizard import BTWizardScreen
        from input.handler import ButtonEvent

        wizard = BTWizardScreen()
        initial_focus = wizard._menu_nav.focus_index

        result = wizard.handle_event(ButtonEvent.SHORT_PRESS)
        self.assertTrue(result)
        self.assertEqual(wizard._menu_nav.focus_index, initial_focus + 1)

    def test_handle_event_returns_false_for_unknown(self):
        from screens.bt_wizard import BTWizardScreen
        wizard = BTWizardScreen()

        # Pass something not in the map
        result = wizard.handle_event("unknown_event")
        self.assertFalse(result)


class TestBTWizardScanning(unittest.TestCase):
    """Tests for scan flow."""

    def test_start_scan_without_bt(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen(bt_service=None)
        wizard._start_scan()

        # Without BT, should transition to SELECT_DEVICE with empty list
        self.assertEqual(wizard._state, WizardState.SELECT_DEVICE)
        self.assertEqual(wizard._found_devices, [])

    def test_start_scan_with_unavailable_bt(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        svc = _make_mock_bt_service(is_available=False)
        wizard = BTWizardScreen(bt_service=svc)
        wizard._start_scan()

        self.assertEqual(wizard._state, WizardState.SELECT_DEVICE)

    def test_show_paired_devices(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        dev = _make_mock_device(name="Paired Device")
        dev.paired = True
        svc = _make_mock_bt_service()
        svc.known_devices = {"AA:BB:CC:DD:EE:FF": dev}

        wizard = BTWizardScreen(bt_service=svc)
        wizard._show_paired()

        self.assertEqual(wizard._state, WizardState.SELECT_DEVICE)
        self.assertEqual(len(wizard._found_devices), 1)


class TestBTWizardPairing(unittest.TestCase):
    """Tests for pairing flow."""

    def test_start_pairing_without_bt(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        dev = _make_mock_device()
        wizard = BTWizardScreen(bt_service=None)
        wizard._start_pairing(dev)

        self.assertEqual(wizard._state, WizardState.FAILED)
        self.assertEqual(wizard._error_message, "BT NOT AVAILABLE")

    def test_start_pairing_with_unavailable_bt(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        dev = _make_mock_device()
        svc = _make_mock_bt_service(is_available=False)
        wizard = BTWizardScreen(bt_service=svc)
        wizard._start_pairing(dev)

        self.assertEqual(wizard._state, WizardState.FAILED)


class TestBTWizardRender(unittest.TestCase):
    """Tests for rendering — verifies no crash, not pixel-perfect."""

    def _make_surface(self):
        return pygame.Surface((240, 280))

    def test_render_menu(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        wizard._state = WizardState.MENU
        surface = self._make_surface()
        wizard.render(surface)  # Should not raise

    def test_render_scanning(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        import time
        wizard = BTWizardScreen()
        wizard._state = WizardState.SCANNING
        wizard._scan_start_time = time.monotonic()
        surface = self._make_surface()
        wizard.render(surface)

    def test_render_select_device_empty(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        wizard._state = WizardState.SELECT_DEVICE
        wizard._found_devices = []
        surface = self._make_surface()
        wizard.render(surface)

    def test_render_select_device_with_devices(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        dev1 = _make_mock_device(name="AirPods Pro", rssi=-42)
        dev2 = _make_mock_device(name="JBL Speaker", address="11:22:33:44:55:66", rssi=-65)
        wizard = BTWizardScreen()
        wizard._state = WizardState.SELECT_DEVICE
        wizard._found_devices = [dev1, dev2]
        wizard._device_nav = wizard._build_device_nav()
        surface = self._make_surface()
        wizard.render(surface)

    def test_render_pairing(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        import time
        wizard = BTWizardScreen()
        wizard._state = WizardState.PAIRING
        wizard._selected_device = _make_mock_device()
        wizard._scan_start_time = time.monotonic()
        surface = self._make_surface()
        wizard.render(surface)

    def test_render_connected(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        wizard._state = WizardState.CONNECTED
        wizard._connected_info = {"name": "AirPods Pro", "address": "AA:BB:CC:DD:EE:FF", "is_airpods": True}
        wizard._connected_nav = wizard._build_connected_nav()
        surface = self._make_surface()
        wizard.render(surface)

    def test_render_failed(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        wizard._state = WizardState.FAILED
        wizard._error_message = "TIMEOUT"
        wizard._selected_device = _make_mock_device()
        surface = self._make_surface()
        wizard.render(surface)

    def test_render_menu_with_connected_device(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        dev = _make_mock_device(name="My AirPods")
        svc = _make_mock_bt_service(connected_device=dev)
        wizard = BTWizardScreen(bt_service=svc)
        wizard._state = WizardState.MENU
        surface = self._make_surface()
        wizard.render(surface)


class TestBTWizardLifecycle(unittest.TestCase):
    """Tests for on_enter / on_exit."""

    def test_on_enter_resets_state(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        wizard._state = WizardState.CONNECTED  # Some other state
        wizard.on_enter()
        self.assertEqual(wizard._state, WizardState.MENU)

    def test_on_exit_cancels_tasks(self):
        from screens.bt_wizard import BTWizardScreen
        wizard = BTWizardScreen()

        mock_scan = MagicMock()
        mock_scan.done.return_value = False
        wizard._scan_task = mock_scan

        mock_pair = MagicMock()
        mock_pair.done.return_value = False
        wizard._pair_task = mock_pair

        wizard.on_exit()

        mock_scan.cancel.assert_called_once()
        mock_pair.cancel.assert_called_once()

    def test_on_exit_no_tasks(self):
        from screens.bt_wizard import BTWizardScreen
        wizard = BTWizardScreen()
        wizard.on_exit()  # Should not raise


class TestBTWizardHints(unittest.TestCase):
    """Tests for hint text."""

    def test_scanning_hint(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        wizard._state = WizardState.SCANNING
        self.assertIn("cancel", wizard.get_hint().lower())

    def test_failed_hint(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        wizard._state = WizardState.FAILED
        hint = wizard.get_hint().lower()
        self.assertIn("retry", hint)
        self.assertIn("back", hint)

    def test_menu_hint(self):
        from screens.bt_wizard import BTWizardScreen, WizardState
        wizard = BTWizardScreen()
        wizard._state = WizardState.MENU
        hint = wizard.get_hint().lower()
        self.assertIn("select", hint)


if __name__ == "__main__":
    unittest.main()
