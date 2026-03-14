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
echo "  Gear icon → hostname=bitos, SSH=yes, WiFi=your network"
echo ""
read -p "Press ENTER when SD card is mounted as 'bootfs'..."

if [ ! -d "/Volumes/bootfs" ]; then
  echo "ERROR: /Volumes/bootfs not found"
  echo "Make sure SD card is inserted and mounted"
  exit 1
fi

echo "Copying cloud-init config..."
cp "$CLOUD_INIT" /Volumes/bootfs/user-data
echo "✓ cloud-init copied"

diskutil eject /Volumes/bootfs 2>/dev/null || true
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SD CARD READY"
echo ""
echo "  1. Insert SD into Pi"
echo "  2. Press PiSugar power button"
echo "  3. Wait 15 minutes (auto-install)"
echo "  4. ssh pi@bitos"
echo "  5. bash ~/bitos/scripts/day_one.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
