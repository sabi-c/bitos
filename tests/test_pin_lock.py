"""Tests for PIN lock screen and change-PIN panel."""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.lock import LockScreen
from screens.panels.change_pin import ChangePinPanel
from storage.repository import DeviceRepository


class PinLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = DeviceRepository(db_path=str(Path(self.tmp.name) / "bitos.db"))
        self.repo.initialize()
        self.unlocked = False

        def on_home():
            self.unlocked = True

        self.lock = LockScreen(on_home=on_home, repository=self.repo)
        # Bypass time-based flash blocking in tests
        self.lock._flash_until = 0.0

    def tearDown(self):
        self.tmp.cleanup()

    def test_correct_pin_unlocks(self):
        """Default PIN 1234 should unlock."""
        # Digit 1: cycle to 1, confirm
        self.lock.handle_action("SHORT_PRESS")  # 0->1
        self.lock.handle_action("DOUBLE_PRESS")  # confirm 1

        # Digit 2: cycle to 2, confirm
        self.lock.handle_action("SHORT_PRESS")  # 0->1
        self.lock.handle_action("SHORT_PRESS")  # 1->2
        self.lock.handle_action("DOUBLE_PRESS")  # confirm 2

        # Digit 3: cycle to 3, confirm
        self.lock.handle_action("SHORT_PRESS")  # 0->1
        self.lock.handle_action("SHORT_PRESS")  # 1->2
        self.lock.handle_action("SHORT_PRESS")  # 2->3
        self.lock.handle_action("DOUBLE_PRESS")  # confirm 3

        # Digit 4: cycle to 4, confirm (auto-verify on 4th digit)
        self.lock.handle_action("SHORT_PRESS")  # 0->1
        self.lock.handle_action("SHORT_PRESS")  # 1->2
        self.lock.handle_action("SHORT_PRESS")  # 2->3
        self.lock.handle_action("SHORT_PRESS")  # 3->4
        self.lock.handle_action("DOUBLE_PRESS")  # confirm 4 -> auto-verify

        self.assertTrue(self.unlocked)

    def test_wrong_pin_resets(self):
        """Wrong PIN should not unlock and should reset entered digits."""
        # Enter 0000
        for _ in range(4):
            self.lock.handle_action("DOUBLE_PRESS")  # confirm 0 each time

        self.assertFalse(self.unlocked)
        # After flash timeout, entered should be reset
        self.lock._flash_until = 0.0  # clear flash for next test
        self.assertEqual(self.lock._entered, [])

    def test_short_press_cycles_digit(self):
        """SHORT_PRESS should cycle current digit 0->1->2->...->9->0."""
        self.assertEqual(self.lock._current_digit, 0)

        self.lock.handle_action("SHORT_PRESS")
        self.assertEqual(self.lock._current_digit, 1)

        self.lock.handle_action("SHORT_PRESS")
        self.assertEqual(self.lock._current_digit, 2)

        # Cycle all the way around
        for _ in range(8):
            self.lock.handle_action("SHORT_PRESS")
        self.assertEqual(self.lock._current_digit, 0)

    def test_double_press_confirms_digit(self):
        """DOUBLE_PRESS should append current digit to entered list."""
        self.lock.handle_action("SHORT_PRESS")  # digit = 1
        self.lock.handle_action("SHORT_PRESS")  # digit = 2
        self.lock.handle_action("DOUBLE_PRESS")  # confirm 2

        self.assertEqual(self.lock._entered, [2])
        self.assertEqual(self.lock._current_digit, 0)  # reset after confirm

    def test_long_press_deletes_last_digit(self):
        """LONG_PRESS should remove last confirmed digit."""
        # Confirm two digits
        self.lock.handle_action("SHORT_PRESS")  # 1
        self.lock.handle_action("DOUBLE_PRESS")  # confirm 1
        self.lock.handle_action("SHORT_PRESS")  # 1
        self.lock.handle_action("SHORT_PRESS")  # 2
        self.lock.handle_action("DOUBLE_PRESS")  # confirm 2

        self.assertEqual(self.lock._entered, [1, 2])

        self.lock.handle_action("LONG_PRESS")
        self.assertEqual(self.lock._entered, [1])

        self.lock.handle_action("LONG_PRESS")
        self.assertEqual(self.lock._entered, [])

    def test_four_digit_auto_verify(self):
        """After 4th DOUBLE_PRESS, verify is called automatically."""
        # Enter 1234 -- correct default
        digits = [1, 2, 3, 4]
        for d in digits:
            for _ in range(d):
                self.lock.handle_action("SHORT_PRESS")
            self.lock.handle_action("DOUBLE_PRESS")

        self.assertTrue(self.unlocked)

    def test_custom_pin_from_repository(self):
        """Lock screen should read PIN from repository."""
        self.repo.set_setting("device_pin", "5678")
        lock = LockScreen(on_home=lambda: setattr(self, 'unlocked', True), repository=self.repo)

        # Enter 5678
        for d in [5, 6, 7, 8]:
            for _ in range(d):
                lock.handle_action("SHORT_PRESS")
            lock.handle_action("DOUBLE_PRESS")

        self.assertTrue(self.unlocked)

    def test_no_repository_uses_default_pin(self):
        """Without repository, default PIN 1234 should work."""
        unlocked = []
        lock = LockScreen(on_home=lambda: unlocked.append(True))

        for d in [1, 2, 3, 4]:
            for _ in range(d):
                lock.handle_action("SHORT_PRESS")
            lock.handle_action("DOUBLE_PRESS")

        self.assertTrue(unlocked)

    def test_cycling_flag(self):
        """_cycling should be True after SHORT_PRESS, False after DOUBLE_PRESS."""
        self.assertFalse(self.lock._cycling)
        self.lock.handle_action("SHORT_PRESS")
        self.assertTrue(self.lock._cycling)
        self.lock.handle_action("DOUBLE_PRESS")
        self.assertFalse(self.lock._cycling)


class ChangePinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = DeviceRepository(db_path=str(Path(self.tmp.name) / "bitos.db"))
        self.repo.initialize()
        self.went_back = False
        self.panel = ChangePinPanel(
            repository=self.repo,
            on_back=lambda: setattr(self, 'went_back', True),
        )
        self.panel._flash_until = 0.0

    def tearDown(self):
        self.tmp.cleanup()

    def _enter_digits(self, digits):
        """Helper to enter a sequence of digits via SHORT_PRESS + DOUBLE_PRESS."""
        for d in digits:
            for _ in range(d):
                self.panel.handle_action("SHORT_PRESS")
            self.panel.handle_action("DOUBLE_PRESS")
            self.panel._flash_until = 0.0  # clear any flash

    def test_full_pin_change_flow(self):
        """Enter current PIN -> new PIN -> confirm -> saved."""
        # Step 0: enter current PIN (1234)
        self._enter_digits([1, 2, 3, 4])
        self.assertEqual(self.panel._step, 1)

        # Step 1: enter new PIN (5678)
        self._enter_digits([5, 6, 7, 8])
        self.assertEqual(self.panel._step, 2)

        # Step 2: confirm new PIN (5678)
        self._enter_digits([5, 6, 7, 8])

        # PIN should be saved
        self.assertEqual(self.repo.get_setting("device_pin", default="1234"), "5678")
        self.assertTrue(self.went_back)

    def test_wrong_current_pin_stays_on_step_0(self):
        """Wrong current PIN flashes and stays on step 0."""
        self._enter_digits([0, 0, 0, 0])
        self.assertEqual(self.panel._step, 0)
        self.assertEqual(self.panel._entered, [])

    def test_mismatched_confirm_stays_on_step_2(self):
        """Mismatched confirmation flashes and stays on step 2."""
        # Step 0: correct current
        self._enter_digits([1, 2, 3, 4])
        # Step 1: new PIN
        self._enter_digits([5, 6, 7, 8])
        # Step 2: wrong confirm
        self._enter_digits([1, 1, 1, 1])

        self.assertEqual(self.panel._step, 2)
        self.assertEqual(self.repo.get_setting("device_pin", default="1234"), "1234")

    def test_long_press_with_no_digits_goes_back(self):
        """LONG_PRESS with empty entry should go back."""
        self.panel.handle_action("LONG_PRESS")
        self.assertTrue(self.went_back)


if __name__ == "__main__":
    unittest.main()
