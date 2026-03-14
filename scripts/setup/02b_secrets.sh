#!/bin/bash
set -euo pipefail

sudo mkdir -p /etc/bitos
sudo touch /etc/bitos/secrets
sudo chmod 600 /etc/bitos/secrets
sudo chown root:root /etc/bitos/secrets

SERIAL=$(grep Serial /proc/cpuinfo | awk '{print $3}')
if [ -z "${SERIAL}" ]; then
  SERIAL="unknown-serial"
fi

DEFAULT_PIN="0000"
echo "Enter your PIN (4 digits, default ${DEFAULT_PIN}):"
read -r PIN
PIN=${PIN:-$DEFAULT_PIN}

PIN_HASH=$(PIN="$PIN" python3 - <<'PY'
import os
import bcrypt
print(bcrypt.hashpw(os.environ["PIN"].encode(), bcrypt.gensalt(12)).decode())
PY
)

BLE_SECRET=$(PIN="$PIN" SERIAL="$SERIAL" python3 - <<'PY'
import hashlib
import os
key = hashlib.pbkdf2_hmac(
    "sha256",
    os.environ["PIN"].encode(),
    os.environ["SERIAL"].encode(),
    100000,
    32,
)
print(key.hex())
PY
)

DEVICE_TOKEN=$(python3 -c 'import uuid; print(uuid.uuid4())')

sudo bash -c "cat > /etc/bitos/secrets << EOF
ANTHROPIC_API_KEY=sk-ant-...
BITOS_DEVICE_TOKEN=${DEVICE_TOKEN}
BITOS_PIN_HASH=${PIN_HASH}
BITOS_BLE_SECRET=${BLE_SECRET}
EOF"

echo "Wrote /etc/bitos/secrets with generated BITOS_DEVICE_TOKEN, BITOS_PIN_HASH, and BITOS_BLE_SECRET"
echo "Edit /etc/bitos/secrets and replace ANTHROPIC_API_KEY before starting services."
