#!/bin/bash
# Called by server/api update endpoint
# Also callable directly: bash scripts/ota_update.sh
set -euo pipefail

BITOS_DIR="${BITOS_DIR:-$HOME/bitos}"
VENV="$BITOS_DIR/.venv"
LOG="/var/log/bitos/ota_update.log"
TARGET="${OTA_TARGET:-both}"

mkdir -p "$(dirname "$LOG")"
echo "[$(date)] OTA update starting (target=$TARGET)..." | tee -a "$LOG"

cd "$BITOS_DIR"

git fetch origin main 2>&1 | tee -a "$LOG"
BEHIND=$(git rev-list HEAD..origin/main --count)

if [ "$BEHIND" = "0" ]; then
  echo "[$(date)] Already up to date" | tee -a "$LOG"
  exit 0
fi

echo "[$(date)] $BEHIND commits behind, updating..." | tee -a "$LOG"

git pull origin main 2>&1 | tee -a "$LOG"
NEW_COMMIT=$(git rev-parse --short HEAD)

if git diff HEAD~1 --name-only | grep -q requirements; then
  echo "[$(date)] Requirements changed, updating pip..." | tee -a "$LOG"
  source "$VENV/bin/activate"
  pip install -r requirements.txt -q 2>&1 | tee -a "$LOG"
fi

echo "[$(date)] Restarting services..." | tee -a "$LOG"
if [ "$TARGET" = "server" ]; then
  sudo systemctl restart bitos-server
elif [ "$TARGET" = "device" ]; then
  sudo systemctl restart bitos-device
else
  sudo systemctl restart bitos-server
  sleep 3
  sudo systemctl restart bitos-device
fi

echo "[$(date)] OTA complete. Version: $NEW_COMMIT" | tee -a "$LOG"

sleep 5
curl -sf http://localhost:8000/health > /dev/null && \
  echo "[$(date)] Server healthy ✓" | tee -a "$LOG"
