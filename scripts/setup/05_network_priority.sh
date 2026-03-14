#!/bin/bash
set -euo pipefail

sudo systemctl disable dhcpcd 2>/dev/null || true
sudo systemctl enable NetworkManager
sudo systemctl start NetworkManager
sudo apt-get install -y bluez-tools
grep -q "\[main\]" /etc/NetworkManager/NetworkManager.conf || \
sudo bash -c 'echo -e "\n[main]\nplugins=keyfile" >> /etc/NetworkManager/NetworkManager.conf'
echo "Done. Verify: nmcli connection show"
