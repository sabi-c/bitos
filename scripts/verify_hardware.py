#!/usr/bin/env python3
"""Run on Pi after setup. Checks all hardware is accessible."""
import subprocess
import sys

results: list[str] = []


def check(name, fn):
    try:
        fn()
        results.append(f"  ✓ {name}")
    except Exception as e:
        results.append(f"  ✗ {name}: {e}")


def check_i2c():
    import smbus2

    bus = smbus2.SMBus(1)
    bus.read_byte(0x57)


def check_wm8960():
    import smbus2

    bus = smbus2.SMBus(1)
    bus.read_byte(0x1A)


def check_spi():
    import spidev

    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.close()


def check_gpio():
    import RPi.GPIO as GPIO  # type: ignore

    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(11, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.cleanup()


def check_audio():
    r = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=5)
    out = f"{r.stdout}\n{r.stderr}"
    assert "wm8960" in out.lower()


if __name__ == "__main__":
    check("PiSugar 3 (I2C 0x57)", check_i2c)
    check("WM8960 audio (I2C 0x1A)", check_wm8960)
    check("SPI (ST7789 display)", check_spi)
    check("GPIO P11 (button)", check_gpio)
    check("ALSA WM8960 (speaker)", check_audio)

    print("HARDWARE VERIFICATION")
    print("─" * 30)
    for r in results:
        print(r)

    fails = [r for r in results if "✗" in r]
    print("─" * 30)
    if fails:
        print(f"FAILED: {len(fails)} issue(s). Fix before running BITOS.")
        sys.exit(1)

    print("ALL HARDWARE OK — ready to run BITOS")
