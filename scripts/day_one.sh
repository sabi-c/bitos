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
python scripts/verify_hardware.py

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
bash scripts/setup/fix_bt_airpods.sh

echo ""
echo "Step 4: Start services..."
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
echo "Step 5: Run smoke test..."
bash scripts/smoke_test.sh

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BITOS IS RUNNING"
echo ""
echo "  Hold button → speak → hear response"
echo ""
echo "  Logs: make logs (from Mac)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
