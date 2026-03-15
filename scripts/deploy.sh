#!/bin/bash
set -e

echo "=== BITOS Deploy ==="
cd ~/bitos
git pull
sudo cp docs/pi_config/bitos-device.service /etc/systemd/system/bitos-device.service
sudo cp docs/pi_config/bitos-server.service /etc/systemd/system/bitos-server.service
sudo systemctl daemon-reload
sudo systemctl restart bitos-server
sleep 5
sudo systemctl restart bitos-device
sleep 3
journalctl -u bitos-device -n 10 --no-pager
echo "=== Deploy complete ==="
