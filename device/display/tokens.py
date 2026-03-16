"""
BITOS Design Tokens
All visual constants live here. Single source of truth.
From BITOS_SPEC.md § 2.
"""

# ── Screen Dimensions ──────────────────────────────────────────
PHYSICAL_W = 240
PHYSICAL_H = 280
SCALE = 2  # Desktop simulator scale factor
WINDOW_W = PHYSICAL_W * SCALE
WINDOW_H = PHYSICAL_H * SCALE

SAFE_INSET = 16     # px, content margin from display edges (matches corner radius)
CORNER_RADIUS = SAFE_INSET  # Rounded corner mask radius
FPS = 15

# ── Colors (1-bit monochrome palette) ──────────────────────────
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
DIM1 = (204, 204, 204)   # 80% white
DIM2 = (153, 153, 153)   # 60%
DIM3 = (102, 102, 102)   # 40%
DIM4 = (51, 51, 51)       # 20%
HAIRLINE = (26, 26, 26)   # Subtle borders

# Extended grays (migrated from ui/panels/base.py)
GRAY_08 = (8, 8, 8)
GRAY_0A = (10, 10, 10)
GRAY_11 = (17, 17, 17)
GRAY_1A = (26, 26, 26)
GRAY_22 = (34, 34, 34)
GRAY_33 = (51, 51, 51)
GRAY_44 = (68, 68, 68)
GRAY_55 = (85, 85, 85)
GRAY_66 = (102, 102, 102)
GRAY_AA = (170, 170, 170)

# ── Typography ─────────────────────────────────────────────────
FONT_REGISTRY = {
    "press_start_2p": "assets/fonts/PressStart2P.ttf",
    "monocraft": "assets/fonts/Monocraft.ttf",
}
DEFAULT_FONT_FAMILY = "press_start_2p"
FONT_NAME = "PressStart2P"
FONT_PATH = FONT_REGISTRY[DEFAULT_FONT_FAMILY]

FONT_SIZES = {
    "time_large": 28,
    "timer": 24,
    "title": 22,
    "body": 17,
    "small": 13,
    "hint": 11,
}

# Font size named constants (migrated from ui/font_sizes.py)
FONT_SIZE_TIME_LARGE = 28
FONT_SIZE_TIMER = 24
FONT_SIZE_TITLE = 22
FONT_SIZE_BODY = 17
FONT_SIZE_SIDEBAR_ITEM = 14
FONT_SIZE_CAPTION = 13
FONT_SIZE_SMALL = 13
FONT_SIZE_HINT = 11
FONT_SIZE_STATUS_BAR = 13
FONT_SIZE_PANEL_HEADER = 14

# ── Borders & Padding ─────────────────────────────────────────
BORDER_OUTER = 2   # px, screen edge
BORDER_INNER = 1   # px, panel dividers
BORDER_ROW = 1     # px, list item separators

PAD_ROW = 4        # px, vertical padding inside rows
PAD_WIDGET = 6     # px, padding inside widgets

# ── Layout ─────────────────────────────────────────────────────
SIDEBAR_W = 84     # px, left sidebar panel
CONTENT_W = PHYSICAL_W - SIDEBAR_W  # 156px, right content panel

STATUS_BAR_H = 20  # px, top status bar (inverted: white bg, black text)
ROW_H_MIN = 28     # px, minimum row height (fingertip navigable)
NAV_HEADER_H = 16  # px, panel header with title
