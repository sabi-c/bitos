# HARDWARE API (Single Source of Truth)

This document is the hardware source-of-truth for BITOS.

> Rule: **No hardware code changes should be made before validating names/signatures/ownership here against source.**

## Source files used

- `docs/whisplay/WhisPlay_patched.py` (driver implementation currently in repo)
- `docs/pi_config/config.txt` (boot overlays and bus enablement)
- `device/hardware/battery.py` (PiSugar I2C usage in BITOS)
- `device/audio/pipeline.py` (ALSA device usage in BITOS)
- `device/input/handler.py` (GPIO button polling behavior in BITOS)

## 1) WhisPlayBoard public API

From `class WhisPlayBoard` in `docs/whisplay/WhisPlay_patched.py`, the **public class attributes** are:

- `LCD_WIDTH`
- `LCD_HEIGHT`
- `CornerHeight`
- `DC_PIN`
- `RST_PIN`
- `LED_PIN`
- `RED_PIN`
- `GREEN_PIN`
- `BLUE_PIN`
- `BUTTON_PIN`

Public methods with signatures:

- `set_backlight(brightness)`
- `set_backlight_mode(mode)`
- `set_window(x0, y0, x1, y1, use_horizontal=0)`
- `draw_pixel(x, y, color)`
- `draw_line(x0, y0, x1, y1, color)`
- `fill_screen(color)`
- `draw_image(x, y, width, height, pixel_data)`
- `set_rgb(r, g, b)`
- `set_rgb_fade(r_target, g_target, b_target, duration_ms=100)`
- `button_pressed()`
- `on_button_press(callback)`
- `on_button_release(callback)`
- `cleanup()`

Notes:

- `WhisPlayBoard` has **no** `.disp` attribute and **no** `.display` attribute in this source file.
- Display push is done via `draw_image(...)` (and primitives like `fill_screen(...)`).

## 2) GPIO pin ownership

### HAT-owned pins (from WhisPlayBoard constants)

| Physical pin (BOARD) | Symbol | Owner / purpose |
|---|---|---|
| 13 | `DC_PIN` | LCD D/C control (WhisPlay display driver) |
| 7  | `RST_PIN` | LCD reset (WhisPlay display driver) |
| 15 | `LED_PIN` | LCD backlight control (WhisPlay display driver) |
| 22 | `RED_PIN` | RGB LED red channel (WhisPlay) |
| 18 | `GREEN_PIN` | RGB LED green channel (WhisPlay) |
| 16 | `BLUE_PIN` | RGB LED blue channel (WhisPlay) |
| 11 | `BUTTON_PIN` | User button input (WhisPlay / BITOS input) |

### SPI-related ownership

- WhisPlay RPi path uses `self.spi.open(0, 0)` (SPI0 CS0).
- Physical pin **11** is also SPI SCLK on Raspberry Pi headers, so interrupt edge detection is unreliable in this hardware layout.
- BITOS therefore polls pin 11 state with `GPIO.input()` at 20ms interval in `device/input/handler.py`.

## 3) I2C address map used by BITOS

| Bus | Address | Device | Evidence |
|---|---|---|---|
| I2C-1 | `0x57` | PiSugar 3 battery/power controller | `device/hardware/battery.py` |

Registers used by BITOS battery monitor:

- `%`: `0x2A`
- status: `0x02` (charging bit mask `0x80`)
- voltage MSB/LSB: `0x22` / `0x23` (optional read)

## 4) ALSA devices and control names

### Devices currently referenced by BITOS

- `hw:0` default ALSA device via `BITOS_AUDIO` in `device/audio/pipeline.py`.
- Capture uses `arecord` with `-D <device>`.
- Playback uses `aplay` with `-D <device>`.

### Overlay / card context

- `dtoverlay=wm8960-soundcard` is enabled in `docs/pi_config/config.txt`.
- WhisPlay driver probes `/proc/asound/cards` for a card containing `wm8960`.

### ALSA control names

No stable control-name list is currently stored in-repo. When generating/refreshing this doc on target hardware, capture:

- `amixer -c <card-index> scontrols`
- `amixer -c <card-index> controls`

and append the exact mixer control names here.

## 5) Required workflow for hardware edits

Before any hardware-layer code change:

1. Confirm target API/pin/address/control in this document.
2. Verify against the referenced source file(s).
3. Update this document first if reality changed.
4. Then update code.

