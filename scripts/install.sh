#!/bin/bash
set -euo pipefail

echo "BITOS INSTALLER"
cd ~/bitos

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -q
pip install -q spidev RPi.GPIO smbus2 psutil sounddevice

# Install Whisplay driver + WM8960 helper script
if [ ! -d /home/pi/Whisplay ]; then
  git clone https://github.com/sabi-c/Whisplay.git /home/pi/Whisplay
fi
if [ -f /home/pi/Whisplay/install_wm8960_drive.sh ]; then
  bash /home/pi/Whisplay/install_wm8960_drive.sh || true
fi

# Set WM8960 mixer levels
bash scripts/set_audio_levels.sh
bash scripts/setup/02b_secrets.sh

if ! grep -q '^WHISPLAY_DRIVER_PATH=' /etc/bitos/secrets 2>/dev/null; then
  sudo sh -c "printf '\nWHISPLAY_DRIVER_PATH=/home/pi/Whisplay/Driver\n' >> /etc/bitos/secrets"
fi


# Apply WM8960 audio defaults after Whisplay driver configuration
bash scripts/set_audio_levels.sh

bash scripts/setup/03_resilience.sh

# Install systemd units from pi config references
sudo cp docs/pi_config/bitos-server.service /etc/systemd/system/bitos-server.service
sudo cp docs/pi_config/bitos-device.service /etc/systemd/system/bitos-device.service
sudo systemctl daemon-reload
sudo systemctl enable bitos-server bitos-device

sudo mkdir -p /etc/bitos
sudo touch /etc/bitos/configured

echo "Done. Add API key: sudo nano /etc/bitos/secrets"
