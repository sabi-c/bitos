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

CORNER_RADIUS = 20  # Rounded corner height in pixels (ST7789 physical)
FPS = 30

# ── Colors (1-bit monochrome palette) ──────────────────────────
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
DIM1 = (204, 204, 204)   # 80% white
DIM2 = (153, 153, 153)   # 60%
DIM3 = (102, 102, 102)   # 40%
DIM4 = (51, 51, 51)       # 20%
HAIRLINE = (26, 26, 26)   # Subtle borders

# ── Typography ─────────────────────────────────────────────────
FONT_NAME = "PressStart2P"
FONT_PATH = "assets/fonts/PressStart2P.ttf"

FONT_SIZES = {
    "title": 10,
    "body": 8,
    "small": 6,
}

# ── Borders & Padding ─────────────────────────────────────────
BORDER_OUTER = 2   # px, screen edge
BORDER_INNER = 1   # px, panel dividers
BORDER_ROW = 1     # px, list item separators

PAD_ROW = 4        # px, vertical padding inside rows
PAD_WIDGET = 6     # px, padding inside widgets

# ── Layout ─────────────────────────────────────────────────────
SIDEBAR_W = 84     # px, left sidebar panel
CONTENT_W = PHYSICAL_W - SIDEBAR_W  # 156px, right content panel

STATUS_BAR_H = 12  # px, top status bar
NAV_HEADER_H = 16  # px, panel header with title
