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


class PairingSessionTests(unittest.TestCase):
    def setUp(self):
        self.secret_hex = "11" * 32
        self.manager = AuthManager(pin_hash="unused", device_serial="serial-123", ble_secret=self.secret_hex)
        self.client = "AA:BB:CC:DD"

    def _hmac_for(self, nonce: str, timestamp: int) -> str:
        msg = bytes.fromhex(nonce) + int(timestamp).to_bytes(8, byteorder="big", signed=False)
        return hmac.new(bytes.fromhex(self.secret_hex), msg, digestmod=hashlib.sha256).hexdigest()

    def test_pairing_session_validate_and_invalidate(self):
        from bluetooth.auth import PairingSession

        ps = PairingSession()
        self.assertFalse(ps.active)
        ps.start("sess-1", "tok-1", int(time.time()) + 120)
        self.assertTrue(ps.active)
        self.assertTrue(ps.validate("sess-1", "tok-1"))
        self.assertFalse(ps.validate("sess-1", "wrong"))
        self.assertFalse(ps.validate("wrong", "tok-1"))
        ps.invalidate()
        self.assertFalse(ps.active)

    def test_pairing_session_expires(self):
        from bluetooth.auth import PairingSession

        ps = PairingSession()
        ps.start("sess-1", "tok-1", int(time.time()) - 1)
        self.assertFalse(ps.active)
        self.assertFalse(ps.validate("sess-1", "tok-1"))

    def test_verify_requires_pairing_token_when_session_active(self):
        self.manager.pairing.start("sess-1", "tok-1", int(time.time()) + 120)
        ch = self.manager.get_challenge()
        with self.assertRaises(AuthError) as ctx:
            self.manager.verify_response(
                client_addr=self.client,
                nonce=ch["nonce"],
                response_hex=self._hmac_for(ch["nonce"], ch["timestamp"]),
            )
        self.assertEqual(str(ctx.exception), "PAIRING_TOKEN_REQUIRED")

    def test_verify_rejects_wrong_pairing_token(self):
        self.manager.pairing.start("sess-1", "tok-1", int(time.time()) + 120)
        ch = self.manager.get_challenge()
        with self.assertRaises(AuthError) as ctx:
            self.manager.verify_response(
                client_addr=self.client,
                nonce=ch["nonce"],
                response_hex=self._hmac_for(ch["nonce"], ch["timestamp"]),
                pairing_session_id="sess-1",
                pairing_token="wrong-token",
            )
        self.assertEqual(str(ctx.exception), "INVALID_PAIRING_TOKEN")

    def test_verify_succeeds_with_correct_pairing_token(self):
        self.manager.pairing.start("sess-1", "tok-1", int(time.time()) + 120)
        ch = self.manager.get_challenge()
        token = self.manager.verify_response(
            client_addr=self.client,
            nonce=ch["nonce"],
            response_hex=self._hmac_for(ch["nonce"], ch["timestamp"]),
            pairing_session_id="sess-1",
            pairing_token="tok-1",
        )
        self.assertTrue(self.manager.validate_session_token(token))
        # Pairing session should be invalidated after success
        self.assertFalse(self.manager.pairing.active)

    def test_verify_works_without_pairing_when_no_session_active(self):
        """Existing auth flow still works when no pairing session is active."""
        ch = self.manager.get_challenge()
        token = self.manager.verify_response(
            client_addr=self.client,
            nonce=ch["nonce"],
            response_hex=self._hmac_for(ch["nonce"], ch["timestamp"]),
        )
        self.assertTrue(self.manager.validate_session_token(token))


if __name__ == "__main__":
    unittest.main()
