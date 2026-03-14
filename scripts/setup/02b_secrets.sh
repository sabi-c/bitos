#!/bin/bash
set -euo pipefail

SECRETS=${BITOS_SECRETS_FILE:-/etc/bitos/secrets}
SUDO_BIN=${BITOS_SUDO_BIN:-sudo}

$SUDO_BIN mkdir -p "$(dirname "$SECRETS")"
$SUDO_BIN touch "$SECRETS"
$SUDO_BIN chmod 600 "$SECRETS"
$SUDO_BIN chown root:root "$SECRETS"

ensure_secret() {
  local key="$1"
  local value="$2"
  if $SUDO_BIN grep -q "^${key}=" "$SECRETS" 2>/dev/null; then
    return
  fi
  echo "${key}=${value}" | $SUDO_BIN tee -a "$SECRETS" >/dev/null
}

DEVICE_TOKEN=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
BLE_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
PIN_HASH=$(python3 - <<'PY'
import hashlib

try:
    import bcrypt
except ModuleNotFoundError:
    print("sha256$" + hashlib.sha256(b"0000").hexdigest())
else:
    print(bcrypt.hashpw(b"0000", bcrypt.gensalt(12)).decode())
PY
)

ensure_secret "ANTHROPIC_API_KEY" "sk-ant-..."
ensure_secret "BITOS_DEVICE_TOKEN" "$DEVICE_TOKEN"
ensure_secret "BITOS_PIN_HASH" "$PIN_HASH"
ensure_secret "BITOS_BLE_SECRET" "$BLE_SECRET"

echo "Secrets bootstrap complete: $SECRETS"
echo "Generated (if missing): BITOS_DEVICE_TOKEN, BITOS_PIN_HASH (default PIN 0000), BITOS_BLE_SECRET"
echo "Next step: add your real Anthropic key"
echo "  sudo nano $SECRETS"
echo "  Replace: ANTHROPIC_API_KEY=sk-ant-..."
