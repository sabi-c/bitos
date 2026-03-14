# First Boot Flow Specification

## Objective

Define the deterministic first-boot experience for BITOS so non-technical setup is possible with only device + companion app.

## Entry conditions

A device is considered **first boot** when any required bootstrap secret/config is missing:

- `BITOS_DEVICE_SERIAL`
- `BITOS_DEVICE_TOKEN`
- `BITOS_PAIRING_PIN_HASH`
- Wi-Fi connectivity profile

## First boot state machine

1. **Boot diagnostics**
   - Validate display, input button, filesystem writeability, and config presence.
2. **Setup required screen**
   - Full-screen instruction: open companion app and start pairing.
3. **Temporary discoverability window**
   - BLE discoverable for 120s.
   - Passkey overlay blocks normal input when pairing handshake starts.
4. **Auth + secure session**
   - Companion performs challenge-response auth.
5. **Wi-Fi provisioning**
   - Companion writes encrypted SSID/password payload.
6. **Connectivity verification**
   - Device attempts join; reports success/failure to companion.
7. **Finalize**
   - Persist settings, disable discoverability, continue to lock/home flow.

## Input behavior constraints

- SHORT (<600ms): advance UI hint/state when safe.
- LONG (>=600ms): select/confirm current primary action.
- DOUBLE: go back when allowed.
- TRIPLE: reserved for Quick Capture outside provisioning-critical steps.

## Failure handling

- Pairing timeout: return to setup required screen and allow retry.
- Auth failure (3x): apply 30s lockout, show cooldown timer.
- Wi-Fi join failure: retain setup flow, allow retry/edit network.

## Observability

Record first-boot milestones as structured events (timestamped) for diagnostics:

- setup_started
- pairing_started
- pairing_succeeded / pairing_failed
- auth_succeeded / auth_failed
- wifi_write_received
- wifi_connected / wifi_failed
- setup_completed

## Non-goals

- OTA update installation
- Full account sign-in system
- Background app sync before provisioning completes

## Part 10: Optional — Offline AI

For voice that works without internet:
  ssh pi@bitos
  bash ~/bitos/scripts/setup/06_offline_ai.sh

Takes ~10 min. Adds:
- Piper TTS (speaks offline, ~63MB model)
- whisper.cpp STT (transcribes offline, ~75MB model)

After install: device degrades gracefully when WiFi drops.
