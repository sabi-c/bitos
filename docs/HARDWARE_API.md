# BITOS Hardware API Reference

## Platform

- Board: Raspberry Pi Zero 2W Rev 1.0
- SoC: BCM2837 (ARM64)
- RAM: 512MB
- OS: Raspberry Pi OS Lite 64-bit (Bookworm)

## GPIO Pin Map

| BCM | Physical | Owner | Purpose |
|-----|----------|-------|---------|
| 8   | 24 | SPI0 | Chip select 0 (`/dev/spidev0.0`) |
| 7   | 26 | SPI0 | Chip select 1 (`/dev/spidev0.1`) |
| 11  | 23 | SPI0 + WhisPlay button path | SPI clock and shared button line (do not edge-trigger) |
| 10  | 19 | SPI0 | MOSI for display transfers |
| 9   | 21 | SPI0 | MISO |
| 27  | 13 | WhisPlayBoard `DC_PIN` | ST7789 data/command |
| 4   | 7  | WhisPlayBoard `RST_PIN` | ST7789 reset |
| 22  | 15 | WhisPlayBoard `LED_PIN` | LCD backlight PWM |
| 25  | 22 | WhisPlayBoard `RED_PIN` | RGB LED red |
| 24  | 18 | WhisPlayBoard `GREEN_PIN` | RGB LED green |
| 23  | 16 | WhisPlayBoard `BLUE_PIN` | RGB LED blue |
| 17  | 11 | WhisPlayBoard `BUTTON_PIN` | User button polling input |

## I2C Devices (Bus 1)

| Address | Device | Purpose |
|---------|--------|---------|
| 0x18    | WM8960 | Audio codec |
| 0x57    | PiSugar 3 | Battery management |
| 0x68    | DS3231 | RTC (inside PiSugar) |

## SPI Devices

- `/dev/spidev0.0` — ST7789 display via WhisPlayBoard
- `/dev/spidev0.1` — available

## Audio (WM8960)

- Card: `wm8960-soundcard` (index `0`)
- ALSA device: `hw:0,0` (BITOS service uses `BITOS_AUDIO=hw:0`)
- Required runtime mode: `channels=2` (stereo), `rate=48000`, `format=S16_LE`
- Record example: `arecord -D hw:0,0 -f S16_LE -r 48000 -c 2`
- Playback example: `pygame.mixer.init(frequency=48000, size=-16, channels=2)`

## Battery (PiSugar 3)

- I2C: `bus=1`, `addr=0x57`
- Percentage: `reg 0x2a` (0–100)
- Voltage: `((reg[0x22] & 0x3f) << 8 | reg[0x23]) / 1000.0`
- Status: `reg 0x02`, `bit7=charging`, `bit6=USB connected`

## WhisPlayBoard API

Methods from `docs/whisplay/WhisPlay_methods.txt`:

- `__init__(self)` — initialize board peripherals and runtime mode.
- `_button_event_rpi(self, channel)` — internal Raspberry Pi button interrupt handler.
- `_button_monitor_radxa(self)` — internal Radxa button monitor loop.
- `_button_press_event(self, channel)` — dispatch press callback.
- `_button_release_event(self, channel)` — dispatch release callback.
- `_create_rpi_rgb_pwm(self, pin, color_name)` — configure software PWM for one RGB channel.
- `_detect_hardware_version(self)` — detect board/SBC variant.
- `_detect_wm8960(self)` — detect wm8960 ALSA card.
- `_gpio_input(self, pin)` — abstract GPIO read.
- `_gpio_output(self, pin, value)` — abstract GPIO write.
- `_init_display(self)` — initialize ST7789 display controller.
- `_init_radxa(self)` — initialize Radxa GPIO/audio path.
- `_init_rpi(self)` — initialize Raspberry Pi GPIO/audio path.
- `_reset_lcd(self)` — hardware reset for LCD.
- `_rpi_pin_can_drive_low(self, pin)` — capability check for sink-drive pin mode.
- `_rpi_set_backlight_state(self, value)` — set backlight GPIO/PWM state.
- `_rpi_set_rgb_output_state(self, pin, value)` — set RGB output mode.
- `_rpi_set_rgb_sink_state(self, pin, value)` — set RGB sink mode.
- `_send_command(self, cmd, *args)` — send command bytes to ST7789.
- `_send_data(self, data)` — send data bytes to ST7789.
- `button_pressed(self)` — current button pressed-state check.
- `cleanup(self)` — release GPIO/PWM/SPI resources.
- `draw_image(self, x, y, width, height, pixel_data)` — write image framebuffer region.
- `draw_line(self, x0, y0, x1, y1, color)` — draw line primitive.
- `draw_pixel(self, x, y, color)` — draw single pixel.
- `fill_screen(self, color)` — fill full display with one color.
- `on_button_press(self, callback)` — register press callback.
- `on_button_release(self, callback)` — register release callback.
- `set_backlight(self, brightness)` — set backlight brightness level.
- `set_backlight_mode(self, mode)` — set backlight control mode.
- `set_rgb(self, r, g, b)` — set RGB LED state.
- `set_rgb_fade(self, r_target, g_target, b_target, duration_ms=100)` — fade RGB LED values.
- `set_window(self, x0, y0, x1, y1, use_horizontal=0)` — set display write window.

## Critical Rules

1. WhisPlayBoard must initialize **before** any other GPIO access.
2. Do not call `GPIO.cleanup()` before WhisPlayBoard initialization/use.
3. Audio must use **stereo** (`channels=2`) at **48000 Hz**.
