#!/bin/bash
set -euo pipefail

# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Enable Tailscale SSH (replaces regular SSH for remote access)
sudo tailscale up --ssh --accept-dns=false

# Install VNC for screen mirroring (optional, user can skip)
sudo apt-get install -y tigervnc-standalone-server

# Install sqlite-web for remote DB inspection
pip install sqlite-web --break-system-packages

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "TAILSCALE SETUP COMPLETE"
echo "Run: sudo tailscale status"
echo "SSH: ssh pi@$(hostname)"
echo "DB:  run 'make db-web' then visit http://$(hostname):8080"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
