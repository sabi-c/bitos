#!/bin/bash
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BITOS SD CARD PREP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CLOUD_INIT="scripts/cloud-init/user-data"
if grep -q "YOUR_SSH_PUBLIC_KEY_HERE" "$CLOUD_INIT"; then
  echo ""
  echo "⚠ SETUP REQUIRED before flashing:"
  echo ""
  echo "  1. Add your SSH public key:"
  echo "     cat ~/.ssh/id_rsa.pub"
  echo "     Edit $CLOUD_INIT"
  echo ""
  echo "  2. Add your GitHub username to the repo URL"
  echo ""
  read -p "Press ENTER when done, or Ctrl+C to cancel..."
fi

echo ""
echo "Flash SD card with Pi Imager first:"
echo "  OS: Raspberry Pi OS Lite 64-bit (Bookworm)"
echo "  Gear icon → hostname=bitos, SSH=yes"
echo ""
read -p "Press ENTER when SD card is mounted as 'bootfs'..."

if [ ! -d "/Volumes/bootfs" ]; then
  echo "ERROR: /Volumes/bootfs not found"
  echo "Make sure SD card is inserted and mounted"
  exit 1
fi

echo "Copying cloud-init config..."
cp "$CLOUD_INIT" /Volumes/bootfs/user-data
echo "  cloud-init copied"

# Enable SSH on first boot (critical — without this, SSH is disabled)
touch /Volumes/bootfs/ssh
echo "  SSH enabled"

# ── WiFi configuration ───────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  WiFi Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "The Pi needs WiFi to download BITOS on first boot."
echo "You can also configure WiFi in Pi Imager's gear icon."
echo ""
read -p "Configure WiFi now? (y/N) " WIFI_CHOICE

if [[ "$WIFI_CHOICE" =~ ^[Yy] ]]; then
  read -p "WiFi SSID: " WIFI_SSID
  read -sp "WiFi Password: " WIFI_PASS
  echo ""

  if [ -n "$WIFI_SSID" ] && [ -n "$WIFI_PASS" ]; then
    # Find the rootfs volume (may be named differently)
    ROOTFS=""
    for vol in /Volumes/rootfs /Volumes/writable; do
      if [ -d "$vol/etc" ]; then
        ROOTFS="$vol"
        break
      fi
    done

    if [ -z "$ROOTFS" ]; then
      echo ""
      echo "WARNING: rootfs partition not mounted (only bootfs visible)."
      echo "This is normal for some SD readers — WiFi will need to be"
      echo "configured via Pi Imager's gear icon instead."
    else
      NM_DIR="$ROOTFS/etc/NetworkManager/system-connections"
      sudo mkdir -p "$NM_DIR"
      NM_FILE="$NM_DIR/wifi-bitos.nmconnection"
      sudo tee "$NM_FILE" > /dev/null <<WIFIEOF
[connection]
id=wifi-bitos
type=wifi
autoconnect=true
autoconnect-priority=100

[wifi]
ssid=$WIFI_SSID
mode=infrastructure

[wifi-security]
key-mgmt=wpa-psk
psk=$WIFI_PASS

[ipv4]
method=auto

[ipv6]
method=disabled
WIFIEOF
      sudo chmod 600 "$NM_FILE"
      echo "  WiFi config written to SD card"
      echo "  SSID: $WIFI_SSID"
    fi
  else
    echo "  Skipped — SSID or password was empty"
  fi
else
  echo "  Skipped — configure WiFi in Pi Imager or on the Pi later"
fi

# ── Eject ─────────────────────────────────────────────────
echo ""
diskutil eject /Volumes/bootfs 2>/dev/null || true
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SD CARD READY"
echo ""
echo "  1. Insert SD into Pi"
echo "  2. Press PiSugar power button"
echo "  3. Wait 15 minutes (auto-install)"
echo "  4. ssh pi@bitos"
echo "     or: ssh pi@169.254.6.1 (USB)"
echo "  5. bash ~/bitos/scripts/day_one.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
