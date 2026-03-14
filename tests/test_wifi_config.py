import base64
import json
import os
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from bluetooth.auth import AuthError, AuthManager
from bluetooth.characteristics.wifi_config import WiFiConfigCharacteristic, WiFiStatusCharacteristic
from bluetooth.crypto import decrypt_wifi_password, derive_wifi_key
from bluetooth.wifi_manager import WiFiManager


def _has_crypto() -> bool:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401

        return True
    except Exception:
        return False


class WiFiConfigTests(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        self.secret = "22" * 32
        os.environ["BITOS_BLE_SECRET"] = self.secret
        self.auth = AuthManager(pin_hash="x", device_serial="s", ble_secret=self.secret)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def _make_valid_token(self):
        token = "token-ok"
        self.auth._sessions[token] = 9999999999
        return token

    def _encrypt(self, plaintext: str, session_token: str) -> str:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        key = derive_wifi_key(session_token, self.secret)
        nonce = b"123456789012"
        ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ct).decode()

    @unittest.skipUnless(_has_crypto(), "cryptography unavailable")
    def test_valid_write_calls_callback(self):
        called = {}

        def on_wifi_config(ssid, password, security, priority):
            called.update({"ssid": ssid, "password": password, "security": security, "priority": priority})
            return True

        token = self._make_valid_token()
        ch = WiFiConfigCharacteristic(auth_manager=self.auth, on_wifi_config=on_wifi_config)
        payload = {
            "session_token": token,
            "ssid": "STUDIONET-5G",
            "password": self._encrypt("secretpw", token),
            "security": "WPA2",
            "priority": 100,
        }
        ch.WriteValue(json.dumps(payload).encode(), {})
        self.assertEqual(called["ssid"], "STUDIONET-5G")
        self.assertEqual(called["password"], "secretpw")

    def test_invalid_session_token_raises_and_no_callback(self):
        fired = {"called": False}

        def on_wifi_config(*_args):
            fired["called"] = True
            return True

        ch = WiFiConfigCharacteristic(auth_manager=self.auth, on_wifi_config=on_wifi_config)
        payload = {"session_token": "bad", "ssid": "x", "password": "", "security": "OPEN", "priority": 1}
        with self.assertRaises(AuthError):
            ch.WriteValue(json.dumps(payload).encode(), {})
        self.assertFalse(fired["called"])

    def test_wifi_manager_mock_mode_returns_true(self):
        os.environ["BITOS_WIFI"] = "mock"
        mgr = WiFiManager()
        self.assertTrue(mgr.add_or_update_network("SSID", "pw", "WPA2", 100))

    @unittest.skipUnless(_has_crypto(), "cryptography unavailable")
    def test_decrypt_wifi_password_roundtrip(self):
        token = self._make_valid_token()
        encrypted = self._encrypt("abc123", token)
        self.assertEqual(decrypt_wifi_password(encrypted, token, self.secret), "abc123")

    def test_wifi_status_serializes_json_bytes(self):
        status = WiFiStatusCharacteristic()
        status.update({"connected": True, "ssid": "X"})
        raw = status.ReadValue({})
        data = json.loads(raw.decode())
        self.assertTrue(data["connected"])
        self.assertEqual(data["ssid"], "X")


if __name__ == "__main__":
    unittest.main()
