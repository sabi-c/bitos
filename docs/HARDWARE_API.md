# BITOS Hardware API Reference
## Last verified: 2026-03-15

## Platform
Raspberry Pi Zero 2W Rev 1.0 | BCM2837 | 512MB RAM
OS: Raspberry Pi OS Lite 64-bit (Bookworm/Trixie)
Python: 3.13.5

## WhisPlayBoard API
File: /home/pi/Whisplay/Driver/WhisPlay.py
Import: from WhisPlay import WhisPlayBoard

### Methods (verified from live device)
| Method | Signature | Description |
|--------|-----------|-------------|
| draw_image | (x, y, width, height, pixel_data) | Push RGB565 frame to ST7789 |
| fill_screen | (color) | Fill display with solid color |
| set_backlight | (brightness: 0-100) | Set LCD backlight level |
| set_rgb | (r, g, b) | Set RGB LED color |
| set_rgb_fade | (r, g, b, duration_ms=100) | Fade RGB LED |
| on_button_press | (callback: Callable) | Register press callback |
| on_button_release | (callback: Callable) | Register release callback |
| button_pressed | () -> bool | Read current button state |
| cleanup | () | Release GPIO resources |

### Attributes (verified)
- platform: str = 'rpi'
- backlight_mode: bool = True (PWM)
- button_press_callback: Callable | None
- button_release_callback: Callable | None
- previous_frame: bytes | None (frame dedup)
- spi: SpiDev

### Critical Rules
1. Init WhisPlayBoard ONCE via get_board() singleton
2. NO GPIO.cleanup() before WhisPlayBoard init
3. NO GPIO.setmode() before WhisPlayBoard init
4. Button uses GPIO 11 (physical pin 23) — WhisPlayBoard owns it
5. Register button via on_button_press/on_button_release ONLY

## GPIO Pin Map
| BCM | Physical | Owner | Purpose |
|-----|----------|-------|---------|
| 7 | 26 | spi0 CS1 | SPI chip select 1 |
| 8 | 24 | spi0 CS0 | SPI chip select 0 (display) |
| 9 | 21 | WhisPlayBoard | SPI MISO |
| 10 | 19 | WhisPlayBoard | SPI MOSI |
| 11 | 23 | WhisPlayBoard | SPI CLK + Button input |
| 16 | 36 | WhisPlayBoard | RGB LED Blue (input-pulldown mode) |
| 18 | 12 | WhisPlayBoard | RGB LED Green (input-pulldown mode) |
| 22 | 15 | WhisPlayBoard | RGB LED Red (input-pulldown mode) |

## I2C Devices (Bus 1 only — Bus 0 not available)
| Address | Device | Purpose |
|---------|--------|---------|
| 0x1A (UU) | WM8960 | Audio codec (kernel-owned) |
| 0x57 | PiSugar 3 | Battery management |
| 0x68 | DS3231 | RTC (inside PiSugar 3) |

## SPI
- /dev/spidev0.0 — ST7789 display (via WhisPlayBoard)
- /dev/spidev0.1 — available

## Display
- Controller: ST7789
- Resolution: 240x280
- Color: RGB565 (16-bit)
- Interface: SPI0
- Push frame: board.draw_image(0, 0, 240, 280, rgb565_bytes)
- Clear: board.fill_screen(0)
- Backlight: board.set_backlight(0-100)

## Audio (WM8960)
- ALSA card: wm8960-soundcard (index 0)
- ALSA device string: hw:0,0
- REQUIRED format: channels=2 stereo, rate=48000Hz, S16_LE
- Record: arecord -D hw:0,0 -f S16_LE -r 48000 -c 2
- Play: pygame.mixer.pre_init(48000, -16, 2, 4096)
- Key mixer controls:
  - Speaker Playback Volume: max 127 (currently 109)
  - Capture Volume: max 63 (currently 39)
  - Playback Volume: max 255 (currently 255)

## Battery (PiSugar 3)
- I2C: bus=1, addr=0x57
- Percentage: reg 0x2a (0-100, read 100 = 100%)
- Voltage high: reg 0x22
- Voltage low: reg 0x23
- Voltage = ((reg[0x22] & 0x3f) << 8 | reg[0x23]) / 1000.0
- Status: reg 0x02 (bit7=charging)

## Services
- bitos-server: uvicorn on port 8000
- bitos-device: pygame device runtime
- Both enabled and auto-restart
- Device requires server health before starting
