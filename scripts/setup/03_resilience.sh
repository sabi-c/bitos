#!/bin/bash
set -euo pipefail

# log2ram — writes logs to RAM, syncs periodically
# Protects SD card from constant log writes
curl -L https://github.com/azlux/log2ram/archive/master.tar.gz \
    | tar xz -C /tmp
cd /tmp/log2ram-master
sudo ./install.sh

# Increase log2ram size for BITOS (default 40MB is too small)
sudo sed -i 's/SIZE=40M/SIZE=64M/' /etc/log2ram.conf 2>/dev/null || true
sudo sed -i 's/SIZE=128M/SIZE=64M/' /etc/log2ram.conf 2>/dev/null || true

# Also set log rotation for bitos specifically
sudo bash -c 'cat > /etc/logrotate.d/bitos << EOF
/var/log/bitos/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 644 pi pi
}
EOF'

# Hardware watchdog — auto-reboots if system hangs
# Add to /boot/config.txt (or /boot/firmware/config.txt on newer Pi OS)
CONFIG=/boot/config.txt
[ -f /boot/firmware/config.txt ] && CONFIG=/boot/firmware/config.txt
grep -q "dtparam=watchdog=on" "$CONFIG" || \
    echo "dtparam=watchdog=on" | sudo tee -a "$CONFIG"

# systemd watchdog integration
if ! grep -q "RuntimeWatchdogSec=15" /etc/systemd/system.conf; then
  sudo bash -c 'cat >> /etc/systemd/system.conf << EOF
RuntimeWatchdogSec=15
ShutdownWatchdogSec=2min
EOF'
fi

# RAM tmpfs mounts (protect SD card from /tmp and /var/log writes)
# Only add if not already present
grep -q "tmpfs /tmp" /etc/fstab || sudo bash -c 'cat >> /etc/fstab << EOF
tmpfs /tmp       tmpfs defaults,noatime,nosuid,size=64m  0 0
tmpfs /var/tmp   tmpfs defaults,noatime,nosuid,size=16m  0 0
EOF'

echo "RESILIENCE SETUP COMPLETE — reboot required for watchdog"
echo "After reboot, verify: cat /proc/sys/kernel/watchdog"
