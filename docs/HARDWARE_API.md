## WhisPlayBoard

Methods verified from `docs/whisplay/WhisPlay_methods.txt`:

- `__init__(self)`: Initializes GPIO, SPI, display state, backlight, RGB PWM, and button callbacks.
- `_button_event_rpi(self, channel)`: Raspberry Pi interrupt callback that dispatches press/release handlers.
- `_button_monitor_radxa(self)`: Radxa polling loop for button transitions.
- `_button_press_event(self, channel)`: Internal helper that invokes registered press callback.
- `_button_release_event(self, channel)`: Internal helper that invokes registered release callback.
- `_create_rpi_rgb_pwm(self, pin, color_name)`: Creates software PWM for RGB channels on RPi.
- `_detect_hardware_version(self)`: Detects platform variant and sets backlight mode.
- `_detect_wm8960(self)`: Detects WM8960 audio card presence.
- `_gpio_input(self, pin)`: Cross-platform GPIO input wrapper.
- `_gpio_output(self, pin, value)`: Cross-platform GPIO output wrapper.
- `_init_display(self)`: Sends panel init command sequence.
- `_init_radxa(self)`: Configures Radxa GPIO and SPI.
- `_init_rpi(self)`: Configures Raspberry Pi GPIO and SPI.
- `_reset_lcd(self)`: Performs panel hardware reset sequence.
- `_rpi_pin_can_drive_low(self, pin)`: Verifies an RPi GPIO pin can sink current.
- `_rpi_set_backlight_state(self, value)`: Drives active-low backlight pin on RPi.
- `_rpi_set_rgb_output_state(self, pin, value)`: Drives RGB pins in output mode on RPi.
- `_rpi_set_rgb_sink_state(self, pin, value)`: Drives RGB pins with pulldown sink fallback on RPi.
- `_send_command(self, cmd, *args)`: Sends a display command and optional command parameters.
- `_send_data(self, data)`: Sends raw display data bytes over SPI.
- `button_pressed(self)`: Returns current button state (`True` when pressed).
- `cleanup(self)`: Stops PWM, closes SPI, and releases GPIO resources.
- `draw_image(self, x, y, width, height, pixel_data)`: Draws RGB565 image payload in a region.
- `draw_line(self, x0, y0, x1, y1, color)`: Draws a line in RGB565 color.
- `draw_pixel(self, x, y, color)`: Draws a single pixel in RGB565 color.
- `fill_screen(self, color)`: Fills full panel with one RGB565 color.
- `on_button_press(self, callback)`: Registers callback for button press.
- `on_button_release(self, callback)`: Registers callback for button release.
- `set_backlight(self, brightness)`: Sets backlight level (0-100).
- `set_backlight_mode(self, mode)`: Switches between PWM and simple on/off backlight modes.
- `set_rgb(self, r, g, b)`: Sets RGB LED color.
- `set_rgb_fade(self, r_target, g_target, b_target, duration_ms=100)`: Fades RGB LED to target color.
- `set_window(self, x0, y0, x1, y1, use_horizontal=0)`: Sets panel drawing window.

## GPIO Pin Map

| Pin | BCM | Owner | Used For |
|---|---:|---|---|
| 7 | 4 | WhisPlayBoard | LCD reset (`RST_PIN`) |
| 11 | 17 | WhisPlayBoard | User button input (`BUTTON_PIN`) |
| 13 | 27 | WhisPlayBoard | LCD data/command (`DC_PIN`) |
| 15 | 22 | WhisPlayBoard | LCD backlight (`LED_PIN`, active-low) |
| 16 | 23 | WhisPlayBoard | RGB LED blue channel (`BLUE_PIN`) |
| 18 | 24 | WhisPlayBoard | RGB LED green channel (`GREEN_PIN`) |
| 22 | 25 | WhisPlayBoard | RGB LED red channel (`RED_PIN`) |
| 19 | 10 | SPI0 | LCD SPI MOSI |
| 23 | 11 | SPI0 | LCD SPI SCLK |
| 24 | 8 | SPI0 | LCD SPI CE0 |

## I2C Devices

| Address | Bus | Device | Purpose |
|---|---:|---|---|
| `0x1a` | 1 | WM8960 codec (`UU`) | Audio capture/playback codec |
| `0x57` | 1 | PiSugar 3 battery manager | Battery percent/charging/voltage telemetry |
| `0x68` | 1 | RTC (`UU`) | Real-time clock source |

## ALSA

| Card | Device | Controls |
|---|---|---|
| `0: wm8960soundcard (wm8960-soundcard)` | `0: bcm2835-i2s-wm8960-hifi` | Capture Volume, Capture Switch, Playback Volume, Speaker Playback Volume, Headphone Playback Volume, ADC PCM Capture Volume |
| `1: vc4hdmi (vc4-hdmi)` | `0: MAI PCM i2s-hifi-0` | HDMI playback path (no WM8960 mixer controls) |
