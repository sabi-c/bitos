#!/bin/bash
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BITOS COMPLETE SETUP"
echo "  Mac mini backend + Pi device"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [[ "$OSTYPE" != "darwin"* ]]; then
  echo "Run this on your Mac mini."
  exit 1
fi

echo "This script will:"
echo "  1. Set up Mac mini backend (server + Vikunja)"
echo "  2. Prepare your SD card for the Pi"
echo "  3. Give you exact next steps"
echo ""
read -p "Press ENTER to start..."

bash scripts/mac_setup.sh

echo ""
echo "━━━ STEP 2: PREPARE SD CARD ━━━"
echo ""
echo "Now flash the SD card:"
echo "  1. Open Pi Imager"
echo "  2. OS: Raspberry Pi OS Lite (64-bit)"
echo "  3. Gear icon: hostname=bitos, SSH=yes, WiFi=your network"
echo "  4. Flash it"
echo ""
read -p "Press ENTER when flashing is complete..."

bash scripts/flash_sd.sh

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ALL DONE"
echo ""
echo "  Insert SD card → power on Pi → wait 15 min"
echo "  Then: make push-secrets"
echo "  Then: hold button → speak → hear response"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
