import base64
import hashlib
import hmac
import os
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from bluetooth.auth import AuthManager
from bluetooth.crypto import decrypt_wifi_password, derive_wifi_key


class CryptoParityTests(unittest.TestCase):
    def test_derive_wifi_key_is_16_bytes(self):
        key = derive_wifi_key("session-token", "00" * 16)
        self.assertEqual(len(key), 16)

    def test_derive_wifi_key_known_vector(self):
        session_token = "session-token-123"
        ble_secret_hex = "00112233445566778899aabbccddeeff"
        got = derive_wifi_key(session_token, ble_secret_hex).hex()
        self.assertEqual(got, "a462205dfa157f45804dd7d94512130e")

    def test_decrypt_wifi_password_round_trip(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        session_token = "session-xyz"
        ble_secret_hex = "de" * 16
        plaintext = "my-wifi-password"

        key = derive_wifi_key(session_token, ble_secret_hex)
        nonce = b"\x01" * 12
        ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
        payload = base64.b64encode(nonce + ct).decode("ascii")

        out = decrypt_wifi_password(payload, session_token, ble_secret_hex)
        self.assertEqual(out, plaintext)

    def test_auth_manager_challenge_has_nonce_and_timestamp(self):
        mgr = AuthManager(pin_hash="unused", device_serial="SER", ble_secret="11" * 32)
        challenge = mgr.get_challenge()
        self.assertIn("nonce", challenge)
        self.assertIn("timestamp", challenge)
        self.assertEqual(len(challenge["nonce"]), 64)

    def test_auth_manager_verifies_known_hmac(self):
        secret_hex = "22" * 32
        mgr = AuthManager(pin_hash="unused", device_serial="SER", ble_secret=secret_hex)
        challenge = mgr.get_challenge()

        msg = bytes.fromhex(challenge["nonce"]) + int(challenge["timestamp"]).to_bytes(8, byteorder="big", signed=False)
        expected_hmac = hmac.new(bytes.fromhex(secret_hex), msg, digestmod=hashlib.sha256).hexdigest()

        token = mgr.verify_response(client_addr="AA:BB", nonce=challenge["nonce"], response_hex=expected_hmac)
        self.assertTrue(mgr.validate_session_token(token))


if __name__ == "__main__":
    unittest.main()
