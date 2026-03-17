#!/bin/bash
# Ensure Bluetooth audio packages are installed for AirPods support.
# NOTE: Does NOT change ControllerMode — BITOS needs 'dual' for BLE (companion app).
# AirPods scanning uses temporary bredr mode switch in audio_manager.py instead.
set -euo pipefail

echo "[BT] Checking Bluetooth audio packages..."

# Ensure ControllerMode is dual (not bredr) — BLE required for companion app
MAIN_CONF="/etc/bluetooth/main.conf"
if grep -q "^ControllerMode = bredr" "$MAIN_CONF" 2>/dev/null; then
    echo "[BT] Reverting ControllerMode to dual (BLE required for companion app)..."
    sudo sed -i 's/^ControllerMode = bredr/#ControllerMode = dual/' "$MAIN_CONF"
    sudo systemctl restart bluetooth
    sleep 2
    echo "[BT] Bluetooth restarted with dual mode ✓"
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
    systemctl --user enable pipewire pipewire-pulse wireplumber 2>/dev/null || true
    systemctl --user start pipewire pipewire-pulse wireplumber 2>/dev/null || true
    echo "[BT] PipeWire installed and started ✓"
fi

echo "[BT] Bluetooth audio setup complete ✓"
