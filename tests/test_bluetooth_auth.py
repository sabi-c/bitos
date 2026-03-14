import hashlib
import hmac
import time
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from bluetooth.auth import AuthError, AuthManager
from bluetooth.constants import AUTH_LOCKOUT_SECONDS


class BluetoothAuthTests(unittest.TestCase):
    def setUp(self):
        self.secret_hex = "11" * 32
        self.manager = AuthManager(pin_hash="unused", device_serial="serial-123", ble_secret=self.secret_hex)
        self.client = "AA:BB:CC:DD"

    def _hmac_for(self, nonce: str, timestamp: int) -> str:
        msg = bytes.fromhex(nonce) + int(timestamp).to_bytes(8, byteorder="big", signed=False)
        return hmac.new(bytes.fromhex(self.secret_hex), msg, digestmod=hashlib.sha256).hexdigest()

    def test_get_challenge_returns_nonce_and_timestamp(self):
        challenge = self.manager.get_challenge()
        self.assertIn("nonce", challenge)
        self.assertIn("timestamp", challenge)
        self.assertEqual(len(challenge["nonce"]), 64)

    def test_verify_response_succeeds_with_correct_hmac(self):
        ch = self.manager.get_challenge()
        token = self.manager.verify_response(
            client_addr=self.client,
            nonce=ch["nonce"],
            response_hex=self._hmac_for(ch["nonce"], ch["timestamp"]),
        )
        self.assertTrue(self.manager.validate_session_token(token))

    def test_verify_response_fails_with_wrong_hmac_and_increments_counter(self):
        ch = self.manager.get_challenge()
        with self.assertRaises(AuthError):
            self.manager.verify_response(client_addr=self.client, nonce=ch["nonce"], response_hex="00" * 32)
        self.assertEqual(self.manager._attempt_counts.get(self.client), 1)

    def test_verify_response_raises_after_three_failed_attempts(self):
        for _ in range(3):
            ch = self.manager.get_challenge()
            with self.assertRaises(AuthError):
                self.manager.verify_response(client_addr=self.client, nonce=ch["nonce"], response_hex="00" * 32)
        self.assertTrue(self.manager._is_locked_out(self.client))

    def test_verify_response_raises_during_lockout(self):
        self.manager._lockouts[self.client] = time.time() + AUTH_LOCKOUT_SECONDS
        ch = self.manager.get_challenge()
        with self.assertRaises(AuthError) as ctx:
            self.manager.verify_response(client_addr=self.client, nonce=ch["nonce"], response_hex="00" * 32)
        self.assertEqual(str(ctx.exception), "LOCKED_OUT")

    def test_nonce_reuse_raises_auth_error(self):
        ch = self.manager.get_challenge()
        response = self._hmac_for(ch["nonce"], ch["timestamp"])
        self.manager.verify_response(client_addr=self.client, nonce=ch["nonce"], response_hex=response)
        with self.assertRaises(AuthError):
            self.manager.verify_response(client_addr=self.client, nonce=ch["nonce"], response_hex=response)

    def test_expired_nonce_raises_auth_error(self):
        ch = self.manager.get_challenge()
        self.manager._seen_nonces[ch["nonce"]] = time.time() - 1
        with self.assertRaises(AuthError) as ctx:
            self.manager.verify_response(
                client_addr=self.client,
                nonce=ch["nonce"],
                response_hex=self._hmac_for(ch["nonce"], ch["timestamp"]),
            )
        self.assertEqual(str(ctx.exception), "EXPIRED_NONCE")

    def test_valid_session_token_validates(self):
        ch = self.manager.get_challenge()
        token = self.manager.verify_response(
            client_addr=self.client,
            nonce=ch["nonce"],
            response_hex=self._hmac_for(ch["nonce"], ch["timestamp"]),
        )
        self.assertTrue(self.manager.validate_session_token(token))

    def test_expired_session_token_fails_validation(self):
        token = "tok"
        self.manager._sessions[token] = time.time() - 1
        self.assertFalse(self.manager.validate_session_token(token))


if __name__ == "__main__":
    unittest.main()
