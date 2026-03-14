# BITOS · SECURITY DECISIONS
## docs/planning/SECURITY_DECISIONS.md
## Append-only — add new decisions, never edit existing ones
## Format: ## SD-NNN · Title · Date

---

## PURPOSE

Every security-relevant decision made in this project lives here.
This is not a to-do list — it's a record of choices already made,
the threat they address, the alternatives rejected, and the reasoning.

When making a new security decision:
1. Add an entry here BEFORE implementing
2. Reference the SD number in code comments: `# SD-003`
3. Add a corresponding ADR in docs/adr/ if it affects architecture

---

## SD-001 · BLE Pairing: LESC Passkey over Just Works · 2026-03

**Decision:** Use LE Secure Connections (LESC) with Passkey Entry
for Bluetooth pairing. A 6-digit code is displayed on the BITOS
screen and entered on the phone.

**Threat addressed:** Man-in-the-middle attack during BLE pairing.
An attacker in range during pairing could intercept and relay
messages between device and phone, establishing separate encrypted
sessions with each.

**Rejected alternatives:**
- Just Works pairing — no MITM protection, industry consensus is
  that it should not be used for anything sensitive
- Numeric Comparison — requires display on both sides; companion
  app could implement this in v2 if desired

**Implementation:** BlueZ pairing agent with CAPABILITY=DisplayYesNo.
Passkey shown on BITOS screen as a full-screen overlay that blocks
all other input until pairing completes or times out (60s).

---

## SD-002 · BLE Auth: HMAC-SHA256 Session Tokens · 2026-03

**Decision:** All write operations to protected BLE characteristics
require a session token derived via HMAC-SHA256 challenge-response.
The device PIN never transits the air.

**Threat addressed:** Replay attacks and unauthorized writes from
unpaired devices that are in BLE range.

**Mechanism:**
1. Phone reads AUTH_CHALLENGE (nonce + timestamp)
2. Phone computes HMAC(key=PBKDF2(PIN, serial, 100k), data=nonce+ts)
3. Phone writes AUTH_RESPONSE (HMAC bytes only)
4. Device verifies; issues session token (UUID, TTL 300s)
5. All subsequent writes include session token

**Rejected alternatives:**
- Static pre-shared key — doesn't rotate, single point of failure
- TLS over BLE — significant complexity, BlueZ support patchy
- No application-layer auth — relies entirely on BLE link encryption

**Lockout:** 3 failed auth attempts per connection triggers 30s
lockout. Logged to audit file.

---

## SD-003 · WiFi Credentials: Double Encryption · 2026-03

**Decision:** WiFi passwords written via BLE are encrypted at two
layers: BLE link encryption (LESC, AES-128) AND application-layer
AES-128-GCM using a session-derived key.

**Threat addressed:** BLE link layer compromise. If a future
vulnerability in BLE link encryption is discovered, the application
layer encryption provides a second line of defense.

**Session-derived key:** HKDF(session_token + device_serial) →
32-byte key. Key is never stored; derived fresh each session.

---

## SD-004 · Device-Server Auth: Device Token + Request Signing · 2026-03

**Decision:** The Pi authenticates to the FastAPI backend using
two mechanisms:
1. Static device token in X-Device-Token header (from /etc/bitos/secrets)
2. Per-request HMAC-SHA256 signature of (method + path + body + timestamp + nonce)

**Threat addressed:**
- Token alone: vulnerable to replay if token is leaked
- Signing alone: if token rotates, need key distribution mechanism
- Combined: token identifies the device; signature proves request
  integrity and prevents replay

**Nonce + timestamp:** Backend rejects requests with timestamps
outside ±30s window or seen nonces (stored in memory, TTL 60s).

**Future improvement (v2):** Mutual TLS — both Pi and server
present certificates from a shared private CA. Eliminates static
token entirely.

---

## SD-005 · Secrets Storage: Environment File, Root-Owned · 2026-03

**Decision:** All secrets (API keys, device token, PIN hash) stored
in /etc/bitos/secrets with permissions 600, owner root:root.
Loaded via systemd EnvironmentFile directive. Never in .env files
on disk, never in the git repo.

**Threat addressed:** Secrets exposure via file system access,
git history, log output.

**PIN storage:** bcrypt hash with work factor 12. Salt embedded
in hash. Original PIN is never stored.

**API key rotation procedure:**
1. Generate new key in Anthropic console
2. Write to companion app
3. Companion app pushes to device via authenticated BLE write
   (SETTINGS_WRITE characteristic, PIN auth required)
4. Device writes new value to /etc/bitos/secrets
5. systemd restarts bitos.service automatically
6. Old key revoked in Anthropic console

**Rejected alternatives:**
- .env file in repo directory — too easy to accidentally commit
- Hardcoded in config.py — obvious anti-pattern
- Unencrypted plaintext — unacceptable for API keys

---

## SD-006 · Audit Log: Append-Only, Separate from DB · 2026-03

**Decision:** Every tier-2+ action (send email, add event, any
AI-initiated external action confirmed by user) is written to an
append-only audit log at /var/log/bitos/actions.log, separate from
the SQLite conversation database.

**Threat addressed:** Accountability gap — "did Claude send that
email?" should always be answerable even months later. The SQLite
DB can be modified; a write-only log file is harder to tamper with
without leaving traces.

**Log format (JSON lines):**
```json
{
  "ts": "2026-03-14T09:44:12Z",
  "action": "send_email",
  "tier": 2,
  "draft_shown_ms": 8400,
  "confirmed_by": "button_long_press",
  "to": "joaquin@sss.com",
  "subject_hash": "sha256:abc123...",
  "outcome": "success",
  "session_id": "uuid"
}
```

Note: email subject is hashed (not stored in plaintext) to balance
accountability with privacy.

**Rotation:** RotatingFileHandler, max 10MB per file, keep 5 files.

---

## SD-007 · Discoverability: Off by Default · 2026-03

**Decision:** The device is in BLE non-discoverable mode by default.
It only enters discoverable mode when explicitly triggered by user
via Settings → Pair Companion App, or during first-boot setup.
Discoverable timeout: 120 seconds, then reverts automatically.

**Threat addressed:** Passive scanning — any BLE scanner in range
can see discoverable devices. Keeping the device non-discoverable
prevents it showing up in neighbor's device lists.

**Paired connection:** Once paired, the companion app connects
directly (not via scan) using the stored device address. The device
remains connectable (accepts connections from known addresses) but
not discoverable (doesn't advertise to unknown scanners).

---

## SD-008 · Firewall: Deny All Inbound Except Tailscale + LAN · 2026-03

**Decision:** ufw configured to deny all incoming traffic except:
- Tailscale interface (tailscale0) — unrestricted
- Local subnet (192.168.x.0/24) — for development convenience
- All outbound allowed

**Threat addressed:** External network attacks. The device will
occasionally be on unfamiliar networks (via phone hotspot); the
firewall ensures nothing external can initiate a connection.

**SSH:** Accessible only via Tailscale. Password auth disabled.
Keys only. fail2ban with 3-strike lockout.

---

## SD-009 · Certificate Pinning for Anthropic API · 2026-03

**Decision:** The device pins Anthropic's TLS certificate chain
when making API calls. If the certificate presented doesn't match
the pinned value, the request fails and an alert is logged.

**Threat addressed:** SSL stripping / MITM on the Anthropic API
call. Unlikely on home WiFi; more relevant when device is tethered
to phone on unfamiliar networks.

**Implementation:** Pass `verify=/etc/bitos/anthropic-ca.pem` to
httpx/requests. Update the pinned cert file as part of scheduled
maintenance or when Anthropic's cert rotates.

**Fallback:** If pinned cert check fails, device shows
"API CERTIFICATE ERROR" in chat panel. Does not fall back to
unpinned — fail closed, not open.

---

## SD-010 · SD Card: Physical Security Limitation · 2026-03

**Decision (deferred):** Full-disk LUKS encryption is the correct
solution for SD card physical theft protection but is not implemented
in v1 due to the boot-time key entry problem.

**Threat:** SD card physically removed from device gives attacker
full filesystem access including conversation DB and secrets file.

**Mitigations in v1:**
- Secrets file is root-owned 600
- DB file is owner-only 600
- Conversation content is relatively low-sensitivity

**v2 options (document for future):**
A) LUKS with key stored on PiSugar I2C (elegant, integrated)
B) LUKS with key on USB drive that stays plugged in (practical)
C) SQLCipher (encrypted SQLite, AES-256) for DB only
D) TPM via I2C hat (most secure, requires additional hardware)

Recommendation when revisiting: option A (PiSugar key storage)
since PiSugar is already in the stack.

---

## OPEN SECURITY QUESTIONS

- [ ] Companion app: native iOS (App Store review) vs PWA (Web Bluetooth)
      vs Shortcuts — security implications differ for each
- [ ] Network Extension entitlement for BT PAN on iOS — Apple's
      review process and whether it's worth pursuing
- [ ] Rate limiting on FastAPI backend — not implemented, should be
      before any external exposure
- [ ] SQLCipher for conversation DB — assess performance on Pi Zero 2W
