#!/bin/bash
set -euo pipefail

sudo bash -c 'cat > /etc/systemd/system/bitos.service << EOF
[Unit]
Description=BITOS AI Device
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/bitos
EnvironmentFile=/etc/bitos/secrets
ExecStart=/usr/bin/python3 device/main.py
Restart=always
RestartSec=5
StartLimitIntervalSec=60
StartLimitBurst=5
ExecStartPre=/bin/sh -c "test -f /tmp/bitos_crash.json && mv /tmp/bitos_crash.json /var/log/bitos/last_crash.json || true"
StandardOutput=journal
StandardError=journal
SyslogIdentifier=bitos
MemoryMax=300M
MemorySwapMax=0

[Install]
WantedBy=multi-user.target
EOF'

sudo systemctl daemon-reload
sudo systemctl enable bitos
echo "Service installed. Start with: sudo systemctl start bitos"
echo "View logs: journalctl -u bitos -f"
