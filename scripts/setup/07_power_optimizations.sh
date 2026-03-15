#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="/boot/firmware/config.txt"

append_if_missing() {
  local line="$1"
  if ! grep -qxF "$line" "$CONFIG_FILE"; then
    echo "$line" | sudo tee -a "$CONFIG_FILE" >/dev/null
  fi
}

echo "[power] applying Pi Zero 2W power optimizations"
append_if_missing "gpu_mem=16"
append_if_missing "hdmi_blanking=2"
append_if_missing "hdmi_force_hotplug=0"
append_if_missing "camera_auto_detect=0"
append_if_missing "display_auto_detect=0"
append_if_missing "dtparam=act_led_trigger=none"
append_if_missing "dtparam=act_led_activelow=on"

if command -v raspi-config >/dev/null 2>&1; then
  sudo raspi-config nonint do_memory_split 16 || true
fi

if ! dpkg -s zram-tools >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y zram-tools
fi
sudo systemctl enable zramswap
sudo systemctl restart zramswap

if [ -f /etc/dphys-swapfile ]; then
  sudo dphys-swapfile swapoff || true
  sudo sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
  sudo dphys-swapfile setup
  sudo dphys-swapfile swapon
fi

for svc in triggerhappy avahi-daemon cups ModemManager; do
  if systemctl list-unit-files | grep -q "^${svc}\.service"; then
    sudo systemctl disable --now "$svc" || true
  fi
done

echo "[power] done. reboot required to apply config.txt updates"
