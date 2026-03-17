#!/bin/bash
# Fix Bluetooth config for AirPods compatibility on Pi
# AirPods require ControllerMode = bredr (classic BT, not BLE)
# See: https://github.com/bluez/bluez/issues/514
set -euo pipefail

MAIN_CONF="/etc/bluetooth/main.conf"

echo "[BT] Checking Bluetooth config for AirPods compatibility..."

# Check current ControllerMode
if grep -q "^ControllerMode = bredr" "$MAIN_CONF" 2>/dev/null; then
    echo "[BT] ControllerMode already set to bredr ✓"
else
    echo "[BT] Setting ControllerMode = bredr (required for AirPods)..."
    # Uncomment and set if commented out
    sudo sed -i 's/^#\?ControllerMode.*/ControllerMode = bredr/' "$MAIN_CONF"
    # If the line doesn't exist at all, add it under [General]
    if ! grep -q "^ControllerMode" "$MAIN_CONF"; then
        sudo sed -i '/^\[General\]/a ControllerMode = bredr' "$MAIN_CONF"
    fi
    echo "[BT] Restarting bluetooth service..."
    sudo systemctl restart bluetooth
    sleep 2
    echo "[BT] Bluetooth restarted ✓"
fi

# Check for PipeWire or PulseAudio BT support
if dpkg -l 2>/dev/null | grep -q "libspa-0.2-bluetooth"; then
    echo "[BT] PipeWire Bluetooth support installed ✓"
elif dpkg -l 2>/dev/null | grep -q "pulseaudio-module-bluetooth"; then
    echo "[BT] PulseAudio Bluetooth support installed ✓"
else
    echo "[BT] No Bluetooth audio stack found. Installing PipeWire..."
    sudo apt install -y pipewire pipewire-pulse wireplumber \
        libspa-0.2-bluetooth pipewire-audio-client-libraries
    # Enable for the pi user
    systemctl --user enable pipewire pipewire-pulse wireplumber 2>/dev/null || true
    systemctl --user start pipewire pipewire-pulse wireplumber 2>/dev/null || true
    echo "[BT] PipeWire installed and started ✓"
fi

echo ""
echo "[BT] AirPods fix applied. To pair:"
echo "  1. Open AirPods case, hold back button until white flash"
echo "  2. Run: bluetoothctl scan on"
echo "  3. Wait for AirPods MAC, then:"
echo "     bluetoothctl pair XX:XX:XX:XX:XX:XX"
echo "     bluetoothctl trust XX:XX:XX:XX:XX:XX"
echo "     bluetoothctl connect XX:XX:XX:XX:XX:XX"
