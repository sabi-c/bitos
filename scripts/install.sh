#!/bin/bash
set -euo pipefail

echo "BITOS INSTALLER"
cd ~/bitos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -q
pip install RPi.GPIO spidev smbus2 psutil sounddevice pyaudio -q
bash scripts/setup/02b_secrets.sh

if ! grep -q '^WHISPLAY_DRIVER_PATH=' /etc/bitos/secrets 2>/dev/null; then
  sudo sh -c "printf '\nWHISPLAY_DRIVER_PATH=/home/pi/Whisplay/Driver\n' >> /etc/bitos/secrets"
fi

# wm8960 default mixer levels
amixer -c 0 sset 'Speaker' 90% || true
amixer -c 0 sset 'Headphone' 90% || true
amixer -c 0 sset 'Capture' 80% || true

bash scripts/setup/03_resilience.sh
bash scripts/setup/04_bitos_service.sh
# Ensure systemd units are rewritten with clean environment settings.
sudo systemctl enable bitos-server bitos-device
sudo systemctl daemon-reload
sudo mkdir -p /etc/bitos
sudo touch /etc/bitos/configured
echo "Done. Add API key: sudo nano /etc/bitos/secrets"
