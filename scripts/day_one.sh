#!/bin/bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BITOS DAY ONE SETUP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "Step 1: Verify hardware..."
python ~/bitos/scripts/verify_hardware.py

echo ""
echo "Step 2: Check secrets..."
set +e
bash ~/bitos/scripts/setup/check_secrets.sh
secrets_status=$?
set -e
if [ $secrets_status -ne 0 ]; then
  echo ""
  echo "Add your Anthropic API key:"
  echo "  sudo nano /etc/bitos/secrets"
  echo "  Add line: ANTHROPIC_API_KEY=sk-ant-..."
  echo ""
  read -p "Press ENTER when done..."
  bash ~/bitos/scripts/setup/check_secrets.sh
fi

echo ""
echo "Step 3: Start services..."
sudo systemctl enable bitos-server bitos-device
sudo systemctl start bitos-server
echo "Waiting for server..."
until curl -sf http://localhost:8000/health > /dev/null; do
  sleep 1
  echo -n "."
done
echo " OK"
sudo systemctl start bitos-device

echo ""
echo "Step 4: Run smoke test..."
bash ~/bitos/scripts/smoke_test.sh

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BITOS IS RUNNING"
echo ""
echo "  Hold button → speak → hear response"
echo ""
echo "  Logs: make logs (from Mac)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
