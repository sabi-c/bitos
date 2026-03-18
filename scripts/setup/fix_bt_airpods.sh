#!/bin/bash
# Bluetooth audio setup for AirPods on Pi Zero 2W (Bookworm + PipeWire)
#
# Root causes fixed:
#   1. BlueZ 'Bondable' must be true or link keys aren't stored
#   2. WirePlumber seat-monitoring blocks bluez5 SPA on headless Pi
#   3. AirPods need BR/EDR classic scan (hcitool inq), not BLE scan
#   4. 'Experimental = true' needed for some SSP features
#
# Pairing sequence: hcitool cc → bluetoothctl trust → bluetoothctl pair → bluetoothctl connect
set -euo pipefail

echo "[BT] Setting up Bluetooth audio..."

MAIN_CONF="/etc/bluetooth/main.conf"

# ── Step 1: BlueZ configuration ──────────────────────────────────────
echo "[BT] Configuring BlueZ..."
sudo tee "$MAIN_CONF" > /dev/null << 'EOF'
[General]
ControllerMode = dual
Experimental = true
Bondable = true
JustWorksRepairing = always
FastConnectable = true
Class = 0x200414

[BR]

[LE]

[GATT]

[CSIS]

[AVDTP]

[AVRCP]

[Policy]
AutoEnable=true

[AdvMon]
EOF
sudo systemctl restart bluetooth
sleep 2
echo "[BT] BlueZ configured ✓"

# ── Step 2: PipeWire BT packages ─────────────────────────────────────
if dpkg -l 2>/dev/null | grep -q "libspa-0.2-bluetooth"; then
    echo "[BT] PipeWire Bluetooth support installed ✓"
else
    echo "[BT] Installing PipeWire Bluetooth support..."
    sudo apt install -y pipewire pipewire-pulse wireplumber \
        libspa-0.2-bluetooth pipewire-audio-client-libraries
    systemctl --user enable pipewire pipewire-pulse wireplumber 2>/dev/null || true
    systemctl --user start pipewire pipewire-pulse wireplumber 2>/dev/null || true
    echo "[BT] PipeWire installed ✓"
fi

# ── Step 3: WirePlumber bluetooth config ──────────────────────────────
# Disable seat-monitoring: on headless Pi, logind reports "online" not "active",
# which prevents the bluez5 SPA monitor from starting
echo "[BT] Configuring WirePlumber for headless bluetooth..."
mkdir -p ~/.config/wireplumber/wireplumber.conf.d/
cat > ~/.config/wireplumber/wireplumber.conf.d/bluetooth.conf << 'EOF'
wireplumber.profiles = {
  main = {
    monitor.bluez.seat-monitoring = disabled
  }
}

monitor.bluez.properties = {
    bluez5.roles = [ a2dp_sink a2dp_source hfp_hf hfp_ag ]
    bluez5.codecs = [ sbc sbc_xq aac ]
    bluez5.enable-sbc-xq = true
    bluez5.headset-roles = [ hfp_hf ]
}
EOF
systemctl --user restart wireplumber 2>/dev/null || true
sleep 2
echo "[BT] WirePlumber configured ✓"

# ── Step 4: Enable lingering for headless PipeWire ────────────────────
loginctl enable-linger "$(whoami)" 2>/dev/null || true
echo "[BT] User lingering enabled ✓"

# ── Step 5: Install expect for pairing automation ─────────────────────
if ! command -v expect &>/dev/null; then
    sudo apt install -y expect
fi

# ── Step 6: Install boot reconnect service ────────────────────────────
if [ -f /home/pi/bitos/scripts/bt-reconnect.sh ]; then
    mkdir -p ~/.config/systemd/user/
    cat > ~/.config/systemd/user/bitos-bt-reconnect.service << 'SVCEOF'
[Unit]
Description=Reconnect Bluetooth Audio Devices
After=wireplumber.service
Wants=wireplumber.service

[Service]
Type=oneshot
ExecStart=/home/pi/bitos/scripts/bt-reconnect.sh
RemainAfterExit=yes

[Install]
WantedBy=default.target
SVCEOF
    systemctl --user daemon-reload
    systemctl --user enable bitos-bt-reconnect.service
    echo "[BT] Boot reconnect service enabled ✓"
fi

echo ""
echo "[BT] Bluetooth audio setup complete ✓"
echo ""
echo "To pair AirPods:"
echo "  1. Put AirPods in case, hold back button 15s (amber → white)"
echo "  2. sudo hcitool inq --length=8       # find MAC address"
echo "  3. sudo hcitool cc <MAC>              # create ACL connection"
echo "  4. bluetoothctl trust <MAC>           # trust device"
echo "  5. bluetoothctl pair <MAC>            # pair (stores link key)"
echo "  6. bluetoothctl connect <MAC>         # connect A2DP audio"
