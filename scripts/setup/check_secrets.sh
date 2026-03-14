#!/bin/bash
# Run this to verify secrets are configured correctly
SECRETS=${BITOS_SECRETS_FILE:-/etc/bitos/secrets}
MISSING=0

check() {
  if grep -q "^$1=" "$SECRETS" 2>/dev/null; then
    echo "  ✓ $1"
  else
    echo "  ✗ $1 MISSING"
    MISSING=$((MISSING+1))
  fi
}

echo "Checking $SECRETS..."
check ANTHROPIC_API_KEY
check BITOS_DEVICE_TOKEN
check BITOS_PIN_HASH
check BITOS_BLE_SECRET

if [ $MISSING -eq 0 ]; then
  echo "All secrets configured ✓"
else
  echo "$MISSING secret(s) missing. Run: sudo nano /etc/bitos/secrets"
  exit 1
fi
