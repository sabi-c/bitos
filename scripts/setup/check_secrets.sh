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

# Check ANTHROPIC_API_KEY exists AND has a real value (not placeholder)
if grep -q '^ANTHROPIC_API_KEY=' "$SECRETS" 2>/dev/null; then
  KEY_VAL=$(grep '^ANTHROPIC_API_KEY=' "$SECRETS" | cut -d= -f2)
  if [[ "$KEY_VAL" == "sk-ant-"* ]] || [[ "$KEY_VAL" == "sk-"* ]]; then
    echo "  ✓ ANTHROPIC_API_KEY (real key)"
  else
    echo "  ✗ ANTHROPIC_API_KEY (placeholder — add real key)"
    MISSING=$((MISSING+1))
  fi
else
  echo "  ✗ ANTHROPIC_API_KEY MISSING"
  MISSING=$((MISSING+1))
fi

check BITOS_DEVICE_TOKEN
check BITOS_PIN_HASH
check BITOS_BLE_SECRET

if [ $MISSING -eq 0 ]; then
  echo "All secrets configured ✓"
else
  echo "$MISSING secret(s) missing. Run: sudo nano /etc/bitos/secrets"
  exit 1
fi
