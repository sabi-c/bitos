# Hardware Setup Notes

This document captures boot/reliability learnings from Pi + WhisPlay bring-up.

## Critical GPIO and init ordering

- **GPIO 11 conflicts with SPI CLK**. Do not repurpose GPIO 11 for unrelated button logic when SPI display is active.
- **WhisPlayBoard must initialize first** before custom GPIO button handling.
- **Do not call `GPIO.cleanup()` before WhisPlayBoard init/usage**. Cleanup can tear down pins required by display/audio wiring.
- **Button handling should use polling**, not edge-triggered callbacks, to avoid unstable startup/runtime behavior.

## Required Python hardware packages

Install these packages in the device venv:

```bash
pip install RPi.GPIO spidev smbus2 psutil sounddevice pyaudio
```

## Audio (wm8960)

Set ALSA mixer defaults:

```bash
amixer -c 0 sset 'Speaker' 90%
amixer -c 0 sset 'Headphone' 90%
amixer -c 0 sset 'Capture' 80%
```

Use device string:

- `BITOS_AUDIO=hw:0`

## WhisPlay driver path

Ensure this exists in `/etc/bitos/secrets`:

```bash
WHISPLAY_DRIVER_PATH=/home/pi/Whisplay/Driver/WhisPlay.py
```

## Smoke test after deploy

Run:

```bash
bash scripts/smoke_test.sh
```

Expected result:

- all checks show `✓`
- final status prints `READY`
