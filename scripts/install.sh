#!/bin/bash
# BITOS Full Installer — runs on Pi Zero 2W after git clone
# Called by cloud-init (first boot) or manually: bash ~/bitos/scripts/install.sh
# Flags: --non-interactive  (skip prompts, for cloud-init)
set -euo pipefail

BITOS_DIR="${BITOS_DIR:-$HOME/bitos}"
NON_INTERACTIVE=false
for arg in "$@"; do
    case "$arg" in
        --non-interactive) NON_INTERACTIVE=true ;;
    esac
done

cd "$BITOS_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BITOS INSTALLER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. System packages ──────────────────────────────────────
echo ""
echo "[1/9] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    build-essential python3-dev python3-venv python3-pip \
    python3-gi libgirepository1.0-dev gir1.2-glib-2.0 \
    bluez bluez-tools \
    git curl jq \
    alsa-utils portaudio19-dev \
    libsdl2-dev libsdl2-mixer-dev libsdl2-image-dev libsdl2-ttf-dev \
    network-manager \
    2>&1 | tail -5
echo "  System packages ✓"

# ── 2. Bluetooth audio (PipeWire) ───────────────────────────
echo ""
echo "[2/9] Installing Bluetooth audio stack..."
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
echo "[3/9] Setting up Python environment..."
if [ ! -d .venv ]; then
    python3 -m venv .venv --system-site-packages
fi
source .venv/bin/activate

# Verify venv works
if ! python3 -c "import sys; assert sys.prefix != sys.base_prefix" 2>/dev/null; then
    echo "  ERROR: venv creation failed"
    exit 1
fi

pip install --upgrade pip -q
echo "  Installing server dependencies..."
pip install -r requirements.txt -q

echo "  Installing device dependencies..."
# These MUST succeed — they're critical for device boot
pip install -r requirements-device.txt -q 2>&1 | tail -5
echo "  Python venv ✓"

# ── 4. Whisplay driver + WM8960 audio ──────────────────────
echo ""
echo "[4/9] Setting up audio hardware..."
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
echo "[5/9] Initializing secrets..."
sudo mkdir -p /etc/bitos
sudo chmod 755 /etc/bitos
bash scripts/setup/02b_secrets.sh
echo "  Secrets ✓"

# ── 6. Network (NetworkManager) ─────────────────────────────
echo ""
echo "[6/9] Configuring network..."
bash scripts/setup/05_network_priority.sh || true
echo "  Network ✓"

# ── 7. Resilience (watchdog, log2ram, tmpfs) ────────────────
echo ""
echo "[7/9] Configuring resilience..."
bash scripts/setup/03_resilience.sh
echo "  Resilience ✓"

# ── 8. Systemd services ────────────────────────────────────
echo ""
echo "[8/9] Installing systemd services..."
sudo cp docs/pi_config/bitos-server.service /etc/systemd/system/bitos-server.service
sudo cp docs/pi_config/bitos-device.service /etc/systemd/system/bitos-device.service
sudo systemctl daemon-reload
sudo systemctl enable bitos-server bitos-device
echo "  Services ✓"

# ── 9. Cleanup + validation ─────────────────────────────────
echo ""
echo "[9/9] Validating installation..."

# Remove any one-shot boot fix scripts
sudo rm -f /boot/firmware/fix_bt.sh /boot/fix_bt.sh 2>/dev/null || true

# Set secure file permissions
sudo chmod 600 /etc/bitos/secrets 2>/dev/null || true
# Database directory permissions (will be created on first run)
mkdir -p "$BITOS_DIR/server/data"
chmod 700 "$BITOS_DIR/server/data"

# Mark as configured
sudo touch /etc/bitos/configured

# Validate critical imports
FAILED=""
for mod in pygame numpy httpx cryptography smbus2 qrcode pydub edge_tts psutil; do
    if ! python3 -c "import $mod" 2>/dev/null; then
        FAILED="$FAILED $mod"
    fi
done
if [ -n "$FAILED" ]; then
    echo "  WARNING: Failed to import:$FAILED"
    echo "  Device may not boot correctly"
else
    echo "  All critical imports verified ✓"
fi

# Validate BLE deps (these need system packages)
if python3 -c "import gi; gi.require_version('GLib', '2.0')" 2>/dev/null; then
    echo "  GObject introspection ✓"
else
    echo "  WARNING: python3-gi not working — BLE will use mock mode"
fi

echo "  Cleanup ✓"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  INSTALL COMPLETE"
echo ""
echo "  Next: bash ~/bitos/scripts/day_one.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
