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
bash scripts/setup/03_resilience.sh
bash scripts/setup/04_bitos_service.sh
sudo systemctl enable bitos-server bitos-device
sudo systemctl daemon-reload
sudo mkdir -p /etc/bitos
sudo touch /etc/bitos/configured
echo "Done. Add API key: sudo nano /etc/bitos/secrets"
