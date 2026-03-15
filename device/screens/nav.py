"""
BITOS Navigation Events
Semantic navigation intents that screens respond to.
ScreenManager translates ButtonEvent → NavigationEvent.
Screens never import from device.input.handler directly.
"""


class NavigationEvent:
    NEXT = "next"
    SELECT = "select"
    BACK = "back"
    CAPTURE = "capture"
    POWER = "power"
    HOLD_START = "hold_start"
    HOLD_END = "hold_end"
