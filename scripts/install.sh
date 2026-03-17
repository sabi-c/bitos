#!/bin/bash
# BITOS Full Installer — runs on Pi Zero 2W after git clone
# Called by cloud-init (first boot) or manually: bash ~/bitos/scripts/install.sh
set -euo pipefail

BITOS_DIR="${BITOS_DIR:-$HOME/bitos}"
cd "$BITOS_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BITOS INSTALLER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. System packages ──────────────────────────────────────
echo ""
echo "[1/8] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    build-essential python3-dev python3-venv \
    python3-gi libgirepository1.0-dev gir1.2-glib-2.0 \
    bluez \
    git curl jq \
    alsa-utils \
    2>&1 | tail -3
echo "  System packages ✓"

# ── 2. Bluetooth audio (PipeWire) ───────────────────────────
echo ""
echo "[2/8] Installing Bluetooth audio stack..."
if dpkg -l 2>/dev/null | grep -q "libspa-0.2-bluetooth"; then
    echo "  PipeWire Bluetooth already installed ✓"
else
    sudo apt-get install -y -qq \
        pipewire pipewire-pulse wireplumber \
        libspa-0.2-bluetooth \
        pipewire-audio-client-libraries \
        pulseaudio-utils \
        2>&1 | tail -3
    echo "  PipeWire Bluetooth installed ✓"
fi

# Ensure ControllerMode is dual (BLE needed for companion app)
if grep -q "^ControllerMode = bredr" /etc/bluetooth/main.conf 2>/dev/null; then
    sudo sed -i 's/^ControllerMode = bredr/#ControllerMode = dual/' /etc/bluetooth/main.conf
    sudo systemctl restart bluetooth || true
    echo "  Reverted ControllerMode to dual (BLE required) ✓"
fi

# ── 3. Python venv + packages ───────────────────────────────
echo ""
echo "[3/8] Setting up Python environment..."
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
# Hardware-specific packages (not in requirements.txt)
pip install -q spidev RPi.GPIO smbus2 psutil sounddevice pyaudio bluezero edge-tts qrcode pydub httpx 2>/dev/null || true
echo "  Python venv ✓"

# ── 4. Whisplay driver + WM8960 audio ──────────────────────
echo ""
echo "[4/8] Setting up audio hardware..."
if [ ! -d /home/pi/Whisplay ]; then
    echo "  Cloning Whisplay driver..."
    git clone https://github.com/sabi-c/Whisplay.git /home/pi/Whisplay || {
        echo "  WARNING: Whisplay clone failed — audio may not work"
    }
fi
if [ -f /home/pi/Whisplay/install_wm8960_drive.sh ]; then
    bash /home/pi/Whisplay/install_wm8960_drive.sh || true
fi
bash scripts/set_audio_levels.sh || true
echo "  Audio hardware ✓"

# ── 5. Secrets ──────────────────────────────────────────────
echo ""
echo "[5/8] Initializing secrets..."
bash scripts/setup/02b_secrets.sh
echo "  Secrets ✓"

# ── 6. Resilience (watchdog, log2ram, tmpfs) ────────────────
echo ""
echo "[6/8] Configuring resilience..."
bash scripts/setup/03_resilience.sh
echo "  Resilience ✓"

# ── 7. Systemd services ────────────────────────────────────
echo ""
echo "[7/8] Installing systemd services..."
sudo cp docs/pi_config/bitos-server.service /etc/systemd/system/bitos-server.service
sudo cp docs/pi_config/bitos-device.service /etc/systemd/system/bitos-device.service
sudo systemctl daemon-reload
sudo systemctl enable bitos-server bitos-device
echo "  Services ✓"

# ── 8. Boot fix cleanup ────────────────────────────────────
echo ""
echo "[8/8] Cleaning up..."
# Remove any one-shot boot fix scripts from boot partition
sudo rm -f /boot/firmware/fix_bt.sh /boot/fix_bt.sh 2>/dev/null || true

sudo mkdir -p /etc/bitos
sudo touch /etc/bitos/configured
echo "  Cleanup ✓"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  INSTALL COMPLETE"
echo ""
echo "  Next: bash ~/bitos/scripts/day_one.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
