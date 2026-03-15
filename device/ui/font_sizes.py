"""Central font size constants for 240x280 ST7789 (218 PPI, 1.69").

Press Start 2P renders crisply at multiples of 8 (8, 16, 24, 32).
Intermediate sizes (10, 12) are slightly soft but still readable.
Minimum readable on this display: 8px for hints, 10px for captions.

Hierarchy:
  TIME_LARGE (24) > TITLE (16) > BODY (12) > SIDEBAR (12) > CAPTION (10) > HINT (8)
"""

# Large displays (time, counters)
TIME_LARGE = 24     # 3x native, main clock display
TIMER = 20          # countdown timers, slightly smaller than clock

# Headings
TITLE = 16          # 2x native, crisp, panel titles and headers

# Body content
BODY = 12           # main readable text, sidebar items, list items
SIDEBAR_ITEM = 12   # sidebar menu labels (same as body for readability)

# Secondary
CAPTION = 10        # status bar, secondary info, timestamps
SMALL = 10          # same as caption, labels

# Minimal
HINT = 8            # 1x native, bottom hint bar, lowest acceptable size

# Status bar specific
STATUS_BAR = 10     # time, title, status in top bar

# Panel header
PANEL_HEADER = 12   # right panel header text
