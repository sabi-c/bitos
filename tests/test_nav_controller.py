import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.components import NavItem, VerticalNavController


class VerticalNavControllerTests(unittest.TestCase):
    def test_move_wraps_across_items(self):
        nav = VerticalNavController(
            [
                NavItem(key="one", label="One"),
                NavItem(key="two", label="Two"),
                NavItem(key="three", label="Three"),
            ]
        )

        nav.move(-1)
        self.assertEqual(nav.focus_index, 2)

        nav.move(1)
        self.assertEqual(nav.focus_index, 0)

    def test_activate_focused_skips_disabled_or_missing_action(self):
        calls = {"count": 0}

        def on_select():
            calls["count"] += 1

        nav = VerticalNavController(
            [
                NavItem(key="disabled", label="Disabled", enabled=False, action=on_select),
                NavItem(key="active", label="Active", action=on_select),
            ]
        )

        self.assertFalse(nav.activate_focused())
        self.assertEqual(calls["count"], 0)

        nav.move(1)
        self.assertTrue(nav.activate_focused())
        self.assertEqual(calls["count"], 1)


if __name__ == "__main__":
    unittest.main()
