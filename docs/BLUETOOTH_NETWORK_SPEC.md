# BITOS Bluetooth + Network Provisioning Spec

## Scope

Specification for BLE-assisted provisioning and keyboard/status interactions between companion app and BITOS device.

## Transport profile

- Stack: BlueZ GATT server on BITOS
- Pairing: LE Secure Connections + Passkey Entry
- Discoverability: disabled by default; user-triggered pairing mode only

## Characteristic classes

### 1) Authentication

- `AUTH_CHALLENGE` (read)
  - Returns nonce + timestamp + device serial metadata.
- `AUTH_RESPONSE` (write)
  - Accepts HMAC response for session establishment.
- `AUTH_SESSION` (read/notify optional)
  - Returns short-lived session token and TTL metadata.

### 2) Protected writes (session token required)

- `WIFI_CONFIG` (write)
  - Payload: encrypted SSID/password + token.
  - Behavior: reject unauthenticated/expired tokens with no side effects.
- `KEYBOARD_INPUT` (write)
  - Payload: token + text + target metadata.
  - Behavior: route only to active compose-capable contexts.

### 3) Unprotected reads / status

- `WIFI_STATUS` (read)
  - Current connection summary for setup UX.
- `DEVICE_STATUS` (read/notify)
  - Battery/network/screen snapshot; periodic notify updates.

## Payload conventions

- UTF-8 JSON for application payloads.
- Required fields:
  - `schema_version`
  - `request_id` (uuid)
  - `timestamp_ms`
- Errors include stable `code` and human-readable `message`.

## Security controls

- Session token derived from HMAC challenge-response.
- 3 failed auth attempts trigger 30s lockout.
- Sensitive payloads use app-layer encryption in addition to BLE link encryption.

## Networking behavior

- On Wi-Fi write success, attempt connection immediately.
- Expose last connect attempt state via `WIFI_STATUS`.
- Do not block UI loop while network operations run.

## Test expectations

- Invalid token writes do not mutate network config.
- Notify loop for `DEVICE_STATUS` starts/stops cleanly.
- Mock mode remains deterministic (`BITOS_BLUETOOTH=mock`, `BITOS_WIFI=mock`).
