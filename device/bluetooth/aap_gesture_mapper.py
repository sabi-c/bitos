"""AAP gesture-to-button event mapper for BITOS.

Maps AirPods stem press events (detected via AAP L2CAP protocol) to BITOS
ButtonEvent actions. When the AAP client is connected, its gestures take
priority over AVRCP media key events.

The mapper is configurable — different press types can map to different
button events. Default mapping:
    SINGLE  -> DOUBLE_PRESS  (select, since AVRCP play/pause is ambiguous)
    DOUBLE  -> SHORT_PRESS   (next item)
    TRIPLE  -> LONG_PRESS    (go back)
    LONG    -> TRIPLE_PRESS  (agent overlay)
"""
from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

try:
    from bluetooth.aap_client import AAPPressType
except ImportError:
    AAPPressType = None  # type: ignore[assignment,misc]


# Default AAP press -> button event name mapping.
# Keys are AAPPressType int values (0x05-0x08).
# Values are ButtonEvent name strings matching input.handler.ButtonEvent.
DEFAULT_AAP_MAP: dict[int, str] = {
    0x05: "DOUBLE_PRESS",    # Single stem press -> select
    0x06: "SHORT_PRESS",     # Double stem press -> next item
    0x07: "LONG_PRESS",      # Triple stem press -> go back
    0x08: "TRIPLE_PRESS",    # Long press -> agent overlay
}


class AAPGestureMapper:
    """Translates AAP stem press events into BITOS button events.

    Parameters
    ----------
    on_button : callable
        Function to call with a ButtonEvent when an AAP gesture is mapped.
        Signature: on_button(button_event) where button_event is a ButtonEvent enum.
    gesture_map : dict, optional
        Override the default press-type -> button-event mapping.
    """

    def __init__(
        self,
        on_button: Callable | None = None,
        gesture_map: dict[int, str] | None = None,
    ):
        self._on_button = on_button
        self._map = gesture_map or dict(DEFAULT_AAP_MAP)
        self._active = False

    @property
    def active(self) -> bool:
        """True when the mapper is processing AAP gestures."""
        return self._active

    @active.setter
    def active(self, value: bool):
        self._active = value
        logger.info("[AAP-MAP] Mapper %s", "activated" if value else "deactivated")

    @property
    def gesture_map(self) -> dict[int, str]:
        return dict(self._map)

    def update_map(self, press_value: int, button_event_name: str):
        """Update a single mapping entry."""
        self._map[press_value] = button_event_name
        logger.info("[AAP-MAP] Updated 0x%02X -> %s", press_value, button_event_name)

    def on_stem_press(self, press_value: int) -> None:
        """Handle an AAP stem press event.

        This is designed to be wired as the AAPClient.on_stem_press callback.

        Parameters
        ----------
        press_value : int
            The AAP press type byte value (0x05=single, 0x06=double, etc.)
        """
        if not self._active:
            return

        button_name = self._map.get(press_value)
        if not button_name:
            logger.debug("[AAP-MAP] Unmapped press value: 0x%02X", press_value)
            return

        logger.info("[AAP-MAP] Stem press 0x%02X -> %s", press_value, button_name)

        if self._on_button:
            try:
                # Import ButtonEvent lazily to avoid circular imports
                from input.handler import ButtonEvent
                btn = ButtonEvent[button_name]
                self._on_button(btn)
            except (KeyError, ImportError) as exc:
                logger.error("[AAP-MAP] Failed to map to ButtonEvent: %s", exc)
