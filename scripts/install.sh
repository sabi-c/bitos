#!/bin/bash
set -euo pipefail

echo "BITOS INSTALLER"
cd ~/bitos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -q
bash scripts/setup/02b_secrets.sh
bash scripts/setup/03_resilience.sh
bash scripts/setup/04_bitos_service.sh
sudo systemctl enable bitos-server bitos-device
sudo systemctl daemon-reload
echo "Done. Add API key: sudo nano /etc/bitos/secrets"
