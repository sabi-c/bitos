"""Companion crypto helpers for BLE WiFi payloads."""
from __future__ import annotations

import base64
import hashlib


def _hkdf_sha256(ikm: bytes, info: bytes, length: int) -> bytes:
    import hmac as _hmac

    prk = _hmac.new(b"", ikm, hashlib.sha256).digest()
    out = b""
    t = b""
    counter = 1
    while len(out) < length:
        t = _hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        out += t
        counter += 1
    return out[:length]


def derive_wifi_key(session_token: str, ble_secret_hex: str) -> bytes:
    ble_secret = bytes.fromhex(ble_secret_hex)
    ikm = session_token.encode("utf-8") + ble_secret
    return _hkdf_sha256(ikm=ikm, info=b"wifi-key", length=16)


def decrypt_wifi_password(encrypted_b64: str, session_token: str, ble_secret_hex: str) -> str:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except Exception as exc:  # pragma: no cover - exercised as error path when missing dep
        raise RuntimeError("cryptography package is required for AES-128-GCM decrypt") from exc

    key = derive_wifi_key(session_token, ble_secret_hex)
    data = base64.b64decode(encrypted_b64)
    nonce, ct = data[:12], data[12:]
    return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
