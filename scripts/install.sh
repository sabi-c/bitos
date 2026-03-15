#!/bin/bash
set -euo pipefail

echo "BITOS INSTALLER"
cd ~/bitos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -q
# Set WM8960 mixer levels
amixer -c 0 sset 'Headphone Playback Volume' 109,109 || true
amixer -c 0 sset 'Speaker Playback Volume' 109,109 || true
amixer -c 0 sset 'Playback Volume' 255,255 || true
amixer -c 0 sset 'Capture Volume' 39,39 || true
amixer -c 0 sset 'Capture Switch' on,on || true
amixer -c 0 sset 'Left Boost Mixer LINPUT1 Switch' on || true
amixer -c 0 sset 'Right Boost Mixer RINPUT1 Switch' on || true
amixer -c 0 sset 'Left Input Mixer Boost Switch' on || true
amixer -c 0 sset 'Right Input Mixer Boost Switch' on || true
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
