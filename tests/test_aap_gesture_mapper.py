"""Tests for AAP gesture-to-button event mapper."""
import os
import sys
import unittest
from unittest.mock import MagicMock
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))


class TestAAPGestureMapperInit(unittest.TestCase):
    """Tests for AAPGestureMapper initialization."""

    def test_default_state(self):
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        mapper = AAPGestureMapper()
        self.assertFalse(mapper.active)
        self.assertIsNotNone(mapper.gesture_map)

    def test_default_map_values(self):
        from bluetooth.aap_gesture_mapper import AAPGestureMapper, DEFAULT_AAP_MAP
        mapper = AAPGestureMapper()
        self.assertEqual(mapper.gesture_map, DEFAULT_AAP_MAP)

    def test_custom_map(self):
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        custom = {0x05: "SHORT_PRESS", 0x06: "LONG_PRESS"}
        mapper = AAPGestureMapper(gesture_map=custom)
        self.assertEqual(mapper.gesture_map[0x05], "SHORT_PRESS")
        self.assertEqual(mapper.gesture_map[0x06], "LONG_PRESS")

    def test_gesture_map_is_copy(self):
        """Modifying returned map should not affect internal state."""
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        mapper = AAPGestureMapper()
        m = mapper.gesture_map
        m[0x05] = "TRIPLE_PRESS"
        self.assertNotEqual(mapper.gesture_map[0x05], "TRIPLE_PRESS")


class TestAAPGestureMapperActive(unittest.TestCase):
    """Tests for mapper active state."""

    def test_inactive_does_not_dispatch(self):
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        events = []
        mapper = AAPGestureMapper(on_button=lambda e: events.append(e))
        mapper.active = False

        mapper.on_stem_press(0x05)  # single press
        self.assertEqual(events, [])

    def test_active_dispatches(self):
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        events = []
        mapper = AAPGestureMapper(on_button=lambda e: events.append(e))
        mapper.active = True

        mapper.on_stem_press(0x05)
        self.assertEqual(len(events), 1)

    def test_toggle_active(self):
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        mapper = AAPGestureMapper()
        self.assertFalse(mapper.active)
        mapper.active = True
        self.assertTrue(mapper.active)
        mapper.active = False
        self.assertFalse(mapper.active)


class TestAAPGestureMapperDispatch(unittest.TestCase):
    """Tests for gesture event dispatch."""

    def test_single_press_maps_to_double(self):
        """Default: single stem press -> DOUBLE_PRESS (select)."""
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        events = []
        mapper = AAPGestureMapper(on_button=lambda e: events.append(e))
        mapper.active = True

        mapper.on_stem_press(0x05)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "DOUBLE_PRESS")

    def test_double_press_maps_to_short(self):
        """Default: double stem press -> SHORT_PRESS (next)."""
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        events = []
        mapper = AAPGestureMapper(on_button=lambda e: events.append(e))
        mapper.active = True

        mapper.on_stem_press(0x06)
        self.assertEqual(events[0].name, "SHORT_PRESS")

    def test_triple_press_maps_to_long(self):
        """Default: triple stem press -> LONG_PRESS (back)."""
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        events = []
        mapper = AAPGestureMapper(on_button=lambda e: events.append(e))
        mapper.active = True

        mapper.on_stem_press(0x07)
        self.assertEqual(events[0].name, "LONG_PRESS")

    def test_long_press_maps_to_triple(self):
        """Default: long stem press -> TRIPLE_PRESS (agent overlay)."""
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        events = []
        mapper = AAPGestureMapper(on_button=lambda e: events.append(e))
        mapper.active = True

        mapper.on_stem_press(0x08)
        self.assertEqual(events[0].name, "TRIPLE_PRESS")

    def test_unmapped_value_ignored(self):
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        events = []
        mapper = AAPGestureMapper(on_button=lambda e: events.append(e))
        mapper.active = True

        mapper.on_stem_press(0xFF)
        self.assertEqual(events, [])

    def test_no_callback_does_not_crash(self):
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        mapper = AAPGestureMapper(on_button=None)
        mapper.active = True
        mapper.on_stem_press(0x05)  # Should not raise


class TestAAPGestureMapperUpdateMap(unittest.TestCase):
    """Tests for runtime map updates."""

    def test_update_map(self):
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        mapper = AAPGestureMapper()
        mapper.update_map(0x05, "TRIPLE_PRESS")
        self.assertEqual(mapper.gesture_map[0x05], "TRIPLE_PRESS")

    def test_updated_map_dispatches_new_event(self):
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        events = []
        mapper = AAPGestureMapper(on_button=lambda e: events.append(e))
        mapper.active = True

        mapper.update_map(0x05, "LONG_PRESS")
        mapper.on_stem_press(0x05)

        self.assertEqual(events[0].name, "LONG_PRESS")


class TestDefaultAAPMapConstants(unittest.TestCase):
    """Verify the default map covers all AAP press types."""

    def test_all_press_types_mapped(self):
        from bluetooth.aap_gesture_mapper import DEFAULT_AAP_MAP
        self.assertIn(0x05, DEFAULT_AAP_MAP)  # single
        self.assertIn(0x06, DEFAULT_AAP_MAP)  # double
        self.assertIn(0x07, DEFAULT_AAP_MAP)  # triple
        self.assertIn(0x08, DEFAULT_AAP_MAP)  # long

    def test_map_values_are_valid_button_events(self):
        from bluetooth.aap_gesture_mapper import DEFAULT_AAP_MAP
        from input.handler import ButtonEvent
        valid_names = {e.name for e in ButtonEvent}
        for press_val, btn_name in DEFAULT_AAP_MAP.items():
            self.assertIn(btn_name, valid_names,
                          f"AAP map value '{btn_name}' for 0x{press_val:02X} "
                          f"is not a valid ButtonEvent name")


if __name__ == "__main__":
    unittest.main()
