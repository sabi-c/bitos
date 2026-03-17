import os
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.boot import BootDiagnostics


class BootDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_check_display_returns_true(self):
        d = BootDiagnostics()
        self.assertTrue(d._check_display())

    def test_check_api_key_false_for_test_key(self):
        os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
        d = BootDiagnostics()
        self.assertFalse(d._check_api_key())

    def test_check_api_key_true_for_realish_key(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-real"
        d = BootDiagnostics()
        self.assertTrue(d._check_api_key())

    def test_is_complete_true_when_all_checks_done(self):
        d = BootDiagnostics()
        d.results = {name: True for name in d.CHECKS}
        self.assertTrue(d.is_complete())

    def test_all_critical_passed_true_even_when_api_key_fails(self):
        """api_key is non-critical — device can boot offline."""
        d = BootDiagnostics()
        d.results = {"display": True, "button": True, "api_key": False}
        self.assertTrue(d.all_critical_passed())

    def test_all_critical_passed_false_when_button_fails(self):
        d = BootDiagnostics()
        d.results = {"display": True, "button": False, "api_key": True}
        self.assertFalse(d.all_critical_passed())


if __name__ == "__main__":
    unittest.main()
