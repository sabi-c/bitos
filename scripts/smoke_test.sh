#!/bin/bash
PASS=0; FAIL=0

check() {
    if eval "$2" > /dev/null 2>&1; then
        echo "  ✓ $1"; ((PASS++))
    else
        echo "  ✗ $1"; ((FAIL++))
    fi
}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BITOS SMOKE TEST"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "SERVICES:"
check "bitos-server running" "systemctl is-active bitos-server"
check "bitos-device running" "systemctl is-active bitos-device"
check "server health" "curl -sf http://localhost:8000/health"
echo ""
echo "HARDWARE:"
check "SPI device" "test -c /dev/spidev0.0"
check "I2C bus 1" "test -c /dev/i2c-1"
check "audio card" "aplay -l 2>/dev/null | grep -q wm8960"
check "PiSugar battery" "python3 -c 'import smbus2; b=smbus2.SMBus(1); b.read_byte_data(0x57,0x2a); b.close()'"
echo ""
echo "SOFTWARE:"
check "API key set" "grep -q 'sk-ant' /etc/bitos/secrets"
check "configured flag" "test -f /etc/bitos/configured"
check "Whisplay driver" "test -f /home/pi/Whisplay/Driver/WhisPlay.py"
check "BITOS venv" "test -f /home/pi/bitos/.venv/bin/python"
check "font asset" "test -f /home/pi/bitos/device/assets/fonts/PressStart2P.ttf"
echo ""
echo "SYSTEM:"
check "Tailscale" "tailscale status 2>/dev/null | grep -q Logged"
check "disk space" "python3 -c 'import shutil; assert shutil.disk_usage("/").free > 500*1024*1024'"
check "temp OK" "python3 -c 'assert int(open("/sys/class/thermal/thermal_zone0/temp").read())<80000'"
check "RAM available" "python3 -c 'import psutil; assert psutil.virtual_memory().available > 50*1024*1024'"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  $PASS passed, $FAIL failed"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
[ $FAIL -eq 0 ] && echo "  ✓ BITOS READY" && exit 0
echo "  ✗ NOT READY — fix failures above" && exit 1
