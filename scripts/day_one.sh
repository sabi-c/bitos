#!/bin/bash
# BITOS Day One — run after install.sh to verify hardware, add secrets, and start services
set -e

BITOS_DIR="${BITOS_DIR:-$HOME/bitos}"
cd "$BITOS_DIR"
source .venv/bin/activate

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BITOS DAY ONE SETUP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "Step 1: Verify hardware..."
if [ -f scripts/verify_hardware.py ]; then
    python scripts/verify_hardware.py || echo "  WARNING: Hardware verification had issues (continuing)"
else
    echo "  WARNING: verify_hardware.py not found (skipping)"
fi

echo ""
echo "Step 2: Check secrets..."
set +e
bash scripts/setup/check_secrets.sh
secrets_status=$?
set -e
if [ $secrets_status -ne 0 ]; then
  echo ""
  echo "Add your Anthropic API key:"
  echo "  sudo nano /etc/bitos/secrets"
  echo "  Add line: ANTHROPIC_API_KEY=sk-ant-..."
  echo ""
  read -p "Press ENTER when done..."
  bash scripts/setup/check_secrets.sh
fi

echo ""
echo "Step 3: Fix Bluetooth for AirPods..."
if [ -f scripts/setup/fix_bt_airpods.sh ]; then
    bash scripts/setup/fix_bt_airpods.sh || echo "  WARNING: Bluetooth fix had issues (continuing)"
else
    echo "  WARNING: fix_bt_airpods.sh not found (skipping)"
fi

echo ""
echo "Step 4: Check USB gadget networking..."
if ip link show usb0 >/dev/null 2>&1; then
    USB_IP=$(ip -4 addr show usb0 2>/dev/null | grep -oP 'inet \K[\d.]+' || echo "no IP")
    echo "  usb0 is up — IP: $USB_IP"
else
    if grep -q "modules-load=dwc2,g_ether" /boot/firmware/cmdline.txt 2>/dev/null; then
        echo "  USB gadget configured but usb0 not up — will work after reboot with USB cable"
    else
        echo "  WARNING: USB gadget not configured — run install.sh again or reboot"
    fi
fi

echo ""
echo "Step 5: Check Whisplay audio driver..."
if [ -d /home/pi/Whisplay ]; then
    echo "  Whisplay installed"
else
    echo "  WARNING: Whisplay not installed — WM8960 audio HAT may not work"
    echo "  Audio will still work via USB/HDMI/Bluetooth"
fi

echo ""
echo "Step 6: Start services..."
sudo systemctl enable bitos-server bitos-device
sudo systemctl start bitos-server
echo -n "Waiting for server..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo " OK"
    break
  fi
  echo -n "."
  sleep 1
  if [ "$i" -eq 30 ]; then
    echo ""
    echo "  WARNING: Server not ready after 30s — starting device anyway"
  fi
done
sudo systemctl start bitos-device

echo ""
echo "Step 7: Run smoke test..."
if [ -f scripts/smoke_test.sh ]; then
    bash scripts/smoke_test.sh || echo "  WARNING: Smoke test had issues"
else
    echo "  WARNING: smoke_test.sh not found (skipping)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BITOS IS RUNNING"
echo ""
echo "  Hold button -> speak -> hear response"
echo ""
echo "  Device IPs:"
# WiFi IP
WIFI_IP=$(ip -4 addr show wlan0 2>/dev/null | grep -oP 'inet \K[\d.]+' || echo "not connected")
echo "    WiFi (wlan0):  $WIFI_IP"
# USB gadget IP
USB_IP=$(ip -4 addr show usb0 2>/dev/null | grep -oP 'inet \K[\d.]+' || echo "not connected")
echo "    USB  (usb0):   $USB_IP"
# Hostname
echo "    Hostname:      $(hostname).local"
echo ""
echo "  Connect: ssh pi@$WIFI_IP"
echo "       or: ssh pi@169.254.6.1 (USB)"
echo ""
echo "  Logs: make logs (from Mac)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
