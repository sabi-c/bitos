# BITOS · SECURITY DECISIONS
# Append-only — add new decisions, never edit existing
# Format: ## SD-NNN · Title · Date

## SD-001 · BLE Pairing: LESC Passkey over Just Works · 2026-03
Decision: LE Secure Connections with Passkey Entry.
6-digit code shown on BITOS screen, entered on phone.
Threat: MITM during BLE pairing.
Rejected: Just Works (no MITM protection). Numeric Comparison
(requires display on both sides — possible in v2).
Implementation: BlueZ BitosPairingAgent, CAPABILITY=DisplayYesNo,
passkey shown via PasskeyOverlay, timeout 120s.

## SD-002 · BLE Auth: HMAC-SHA256 Session Tokens · 2026-03
Decision: Per-connection session tokens via challenge-response.
Phone reads nonce+timestamp, computes HMAC(PBKDF2(PIN,serial,100k)),
writes response. Device verifies, issues UUID session token (TTL 300s).
Threat: Replay attacks, unauthorized writes from unpaired devices.
Rejected: Static PSK (single point of failure), TLS over BLE (complex,
patchy BlueZ support), no app-layer auth (link-only = insufficient).
Lockout: 3 failed attempts → 30s lockout, logged.
Impl: device/bluetooth/auth.py AuthManager class.

## SD-003 · WiFi Credentials: Double Encryption · 2026-03
Decision: BLE link encryption (LESC AES-128) + app-layer AES-128-GCM.
Session key: HKDF(session_token + BITOS_BLE_SECRET, "wifi-key", 16 bytes).
Threat: Future BLE link layer vulnerability. Defense in depth.
Impl: device/bluetooth/crypto.py derive_wifi_key + decrypt_wifi_password.

## SD-004 · Device-Server Auth: Token + Request Signing · 2026-03
Decision: X-Device-Token header + per-request HMAC-SHA256 of
(method+path+body+timestamp+nonce). Server rejects ±30s timestamps
and seen nonces (memory store, TTL 60s).
Threat: Token replay, request tampering on home network.
Rejected: Token alone (replay if leaked). Signing alone (no identity).
Future v2: mutual TLS with shared private CA.
Impl: device/client/api.py + server/main.py middleware.

## SD-005 · Secrets Storage: /etc/bitos/secrets · 2026-03
Decision: EnvironmentFile in systemd service. File permissions 600,
owner root:root. Never in .env files or git repo.
PIN: bcrypt hash, work factor 12, salt embedded in hash.
BLE secret: PBKDF2(PIN, serial, 100k) stored as hex — never the PIN.
Rotation: companion app pushes new key via authenticated BLE write
to SETTINGS_WRITE characteristic. Device writes to secrets file,
systemd restarts service automatically.

## SD-006 · Audit Log: Append-Only for Tier-2 Actions · 2026-03
Decision: /var/log/bitos/actions.log, JSON lines format.
RotatingFileHandler: 10MB max, keep 5 files.
Logged fields: ts, action, tier, draft_shown_ms, confirmed_by,
subject_hash (SHA-256, not plaintext), outcome, session_id.
Threat: Accountability gap — "did Claude send that?" must be answerable.
SQLite DB can be modified; write-only log file is harder to tamper.

## SD-007 · BLE Discoverability: Off by Default · 2026-03
Decision: Device non-discoverable unless explicitly triggered.
Triggers: Settings → Pair Companion App, or boot no-network flow.
Timeout: 120s then auto-revert. Between triggers: connectable (known
paired device can connect) but not discoverable (won't appear in scans).
Threat: Passive scanning — neighbors see device in BT lists.

## SD-008 · Firewall: Deny All Inbound Except Tailscale+LAN · 2026-03
Decision: ufw default deny incoming. Allow in on tailscale0.
Allow from 192.168.0.0/16. SSH via Tailscale only after setup.
Password auth disabled, public key only. fail2ban: 3 strikes, 1h ban.
Impl: scripts/setup/02_security.sh

## SD-009 · Certificate Pinning for Anthropic API · 2026-03
Decision: Pin Anthropic TLS cert chain. Fail closed on mismatch.
Pass verify=/etc/bitos/anthropic-ca.pem to httpx calls.
Show "API CERTIFICATE ERROR" in chat panel, do not fall back unpinned.
Threat: SSL MITM — more relevant on phone hotspot/unknown networks.
Update pinned cert file when Anthropic's cert rotates.

## SD-010 · SD Card Physical Security: Deferred to v2 · 2026-03
Decision: LUKS full-disk encryption deferred. Boot-time key entry
problem not yet solved for headless device.
v1 mitigations: secrets file root-owned 600, DB file owner-only 600.
v2 options (in priority order):
  A) LUKS key stored on PiSugar 3 via I2C (elegant, already in stack)
  B) LUKS key on USB drive that stays plugged in (practical)
  C) SQLCipher for DB only (AES-256, drop-in SQLite replacement)
  D) TPM via I2C hat (most secure, requires additional hardware)
Recommendation when revisiting: Option A.

## OPEN QUESTIONS (fill in as decisions are made)
- [ ] iOS companion: native SwiftUI vs PWA — security implications differ
- [ ] Network Extension entitlement for BT PAN on iOS
- [ ] Rate limiting on FastAPI — not yet implemented, needed before external exposure
- [ ] SQLCipher performance on Pi Zero 2W — assess before v2
