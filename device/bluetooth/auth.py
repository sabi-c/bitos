"""BLE HMAC challenge-response authentication manager."""
from __future__ import annotations

import hmac
import os
import time
import uuid

from .constants import (
    AUTH_LOCKOUT_SECONDS,
    MAX_AUTH_ATTEMPTS,
    NONCE_TTL_SECONDS,
    SESSION_TOKEN_TTL_SECONDS,
    TIMESTAMP_TOLERANCE_SECONDS,
)


class PairingSession:
    """Tracks the single active QR pairing session.

    Only one session can be active at a time.  The companion must present
    the correct token (from the QR URL) alongside the HMAC response.
    """

    def __init__(self):
        self._session_id: str | None = None
        self._token: str | None = None
        self._expires: float = 0

    @property
    def active(self) -> bool:
        return self._session_id is not None and time.time() < self._expires

    @property
    def session_id(self) -> str | None:
        return self._session_id if self.active else None

    def start(self, session_id: str, token: str, expires: int) -> None:
        """Register a new pairing session, replacing any previous one."""
        self._session_id = session_id
        self._token = token
        self._expires = float(expires)

    def validate(self, session_id: str, token: str) -> bool:
        """Return True if the given credentials match the active session."""
        if not self.active:
            return False
        return (
            hmac.compare_digest(self._session_id, session_id)  # type: ignore[arg-type]
            and hmac.compare_digest(self._token, token)  # type: ignore[arg-type]
        )

    def invalidate(self) -> None:
        """Clear the active session (after success or manual cancel)."""
        self._session_id = None
        self._token = None
        self._expires = 0


class AuthError(RuntimeError):
    """Raised when BLE auth challenge/response validation fails."""


class AuthManager:
    """Manages challenge-response sessions for protected BLE writes."""

    def __init__(self, pin_hash: str, device_serial: str, ble_secret: str | None = None):
        self._pin_hash = pin_hash
        self._device_serial = device_serial
        # SD-005: BLE HMAC secret is loaded from protected environment configuration.
        self._ble_secret_hex = ble_secret or os.environ.get("BITOS_BLE_SECRET", "")
        self._ble_secret = bytes.fromhex(self._ble_secret_hex) if self._ble_secret_hex else b""
        self._seen_nonces: dict[str, float] = {}
        self._nonce_timestamps: dict[str, int] = {}
        self._sessions: dict[str, float] = {}
        self._attempt_counts: dict[str, int] = {}
        self._lockouts: dict[str, float] = {}
        self.pairing = PairingSession()

    def get_challenge(self) -> dict:
        # SD-002: Challenge nonce/timestamp pair establishes replay-resistant proof-of-possession flow.
        nonce = os.urandom(32).hex()
        now = int(time.time())
        self._seen_nonces[nonce] = time.time() + NONCE_TTL_SECONDS
        self._nonce_timestamps[nonce] = now
        self._cleanup_expired()
        return {"nonce": nonce, "timestamp": now}

    def verify_response(
        self,
        client_addr: str,
        nonce: str,
        response_hex: str,
        pairing_session_id: str | None = None,
        pairing_token: str | None = None,
    ) -> str:
        if self._is_locked_out(client_addr):
            raise AuthError("LOCKED_OUT")

        # If a pairing session is active, the companion MUST present valid
        # pairing credentials.  This prevents someone who intercepts the
        # HMAC secret from authenticating without scanning the QR code.
        if self.pairing.active:
            if pairing_session_id is None or pairing_token is None:
                self._record_failed_attempt(client_addr)
                raise AuthError("PAIRING_TOKEN_REQUIRED")
            if not self.pairing.validate(pairing_session_id, pairing_token):
                self._record_failed_attempt(client_addr)
                raise AuthError("INVALID_PAIRING_TOKEN")

        if nonce not in self._seen_nonces:
            self._record_failed_attempt(client_addr)
            raise AuthError("INVALID_NONCE")

        if self._seen_nonces[nonce] <= time.time():
            self._seen_nonces.pop(nonce, None)
            self._nonce_timestamps.pop(nonce, None)
            self._record_failed_attempt(client_addr)
            raise AuthError("EXPIRED_NONCE")

        ts = self._nonce_timestamps.get(nonce)
        self._seen_nonces.pop(nonce, None)
        self._nonce_timestamps.pop(nonce, None)
        if ts is None:
            self._record_failed_attempt(client_addr)
            raise AuthError("INVALID_NONCE")

        if abs(int(time.time()) - int(ts)) > TIMESTAMP_TOLERANCE_SECONDS:
            self._record_failed_attempt(client_addr)
            raise AuthError("STALE_CHALLENGE")

        if not self._ble_secret:
            self._record_failed_attempt(client_addr)
            raise AuthError("BLE_SECRET_NOT_SET")

        msg = bytes.fromhex(nonce) + int(ts).to_bytes(8, byteorder="big", signed=False)
        # SD-002: HMAC verification gates session-token issuance for all protected BLE writes.
        expected = hmac.new(self._ble_secret, msg, digestmod="sha256").hexdigest()

        if not hmac.compare_digest(expected, response_hex.lower()):
            self._record_failed_attempt(client_addr)
            if self._is_locked_out(client_addr):
                raise AuthError("LOCKED_OUT")
            raise AuthError("INVALID_HMAC")

        token = str(uuid.uuid4())
        self._sessions[token] = time.time() + SESSION_TOKEN_TTL_SECONDS
        self._attempt_counts.pop(client_addr, None)
        self._lockouts.pop(client_addr, None)
        # Pairing session is single-use — invalidate after successful auth.
        self.pairing.invalidate()
        self._cleanup_expired()
        return token

    def validate_session_token(self, token: str) -> bool:
        self._cleanup_expired()
        return token in self._sessions and self._sessions[token] > time.time()

    def _is_locked_out(self, client_addr: str) -> bool:
        unlock_time = self._lockouts.get(client_addr)
        if unlock_time is None:
            return False
        if unlock_time <= time.time():
            self._lockouts.pop(client_addr, None)
            return False
        return True

    def _record_failed_attempt(self, client_addr: str):
        attempts = self._attempt_counts.get(client_addr, 0) + 1
        self._attempt_counts[client_addr] = attempts
        if attempts >= MAX_AUTH_ATTEMPTS:
            self._lockouts[client_addr] = time.time() + AUTH_LOCKOUT_SECONDS

    def _cleanup_expired(self):
        now = time.time()
        expired_nonces = [nonce for nonce, exp in self._seen_nonces.items() if exp <= now]
        for nonce in expired_nonces:
            self._seen_nonces.pop(nonce, None)
            self._nonce_timestamps.pop(nonce, None)

        expired_sessions = [token for token, exp in self._sessions.items() if exp <= now]
        for token in expired_sessions:
            self._sessions.pop(token, None)

        expired_lockouts = [addr for addr, unlock in self._lockouts.items() if unlock <= now]
        for addr in expired_lockouts:
            self._lockouts.pop(addr, None)
