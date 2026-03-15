#!/bin/bash
set -euo pipefail

sudo bash -c 'cat > /etc/systemd/system/bitos-server.service << EOF
[Unit]
Description=BITOS FastAPI Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/bitos
EnvironmentFile=/etc/bitos/secrets
ExecStart=/home/pi/bitos/.venv/bin/uvicorn server.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF'

sudo bash -c 'cat > /etc/systemd/system/bitos-device.service << EOF
[Unit]
Description=BITOS Device Runtime
After=bitos-server.service
Requires=bitos-server.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/bitos
EnvironmentFile=/etc/bitos/secrets
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=SDL_VIDEODRIVER=offscreen
Environment=SDL_FBDEV=/dev/fb0
Environment=BITOS_DISPLAY=st7789
Environment=BITOS_AUDIO=hw:0
Environment=BITOS_BUTTON=gpio
Environment=SERVER_URL=http://localhost:8000
Environment=WHISPLAY_DRIVER_PATH=/home/pi/Whisplay/Driver
Environment=PYTHONPATH=/home/pi/bitos
Environment=PYTHONWARNINGS=ignore::RuntimeWarning
ExecStartPre=/bin/bash -c "until curl -sf http://localhost:8000/health; do sleep 1; done"
ExecStart=/home/pi/bitos/.venv/bin/python -m device.main
Restart=always
RestartSec=5
StartLimitIntervalSec=60
StartLimitBurst=5
MemoryMax=256M
MemorySwapMax=128M
OOMScoreAdjust=500

[Install]
WantedBy=multi-user.target
EOF'

sudo systemctl daemon-reload
sudo systemctl enable bitos-server bitos-device
echo "Services installed. Start with: sudo systemctl start bitos-server bitos-device"
echo "View logs: journalctl -u bitos-server -u bitos-device -f"
