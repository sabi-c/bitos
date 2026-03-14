# Companion App Plan (Phase 7)

## Purpose

Define the companion app scope for onboarding and secure remote controls without requiring shell access to the Pi.

## Platforms

- iOS (primary)
- macOS (shared code where practical)

## Primary jobs-to-be-done

1. **First boot onboarding**
   - Discover BITOS over BLE when pairing mode is enabled.
   - Complete authenticated pairing and establish a secure session.
   - Provision Wi-Fi credentials safely.
2. **Secure device management**
   - Show health/status snapshot (battery, Wi-Fi, backend reachability, active screen).
   - Trigger safe administrative actions (restart service, reboot, rotate secrets) only after explicit confirmation.
3. **Input handoff**
   - Keyboard relay into compose targets on device.
   - Optional prompt handoff from phone to device queue.

## Security requirements

- BLE pairing uses LESC passkey flow (never Just Works).
- Protected writes require valid session token from HMAC challenge-response.
- Wi-Fi credentials use transport + app-layer encryption.
- App must respect lockout behavior after failed auth attempts.

Reference decisions: `docs/planning/SECURITY_DECISIONS.md`.

## UX constraints

- BITOS remains single-button first; companion app is assistive, not required for daily operation.
- Destructive actions require two-step confirmation.
- Show clear success/failure states for every write operation.
- Keep copy terse and operational (diagnostic-first wording).

## MVP scope

- Pair device
- Authenticate session
- Provision Wi-Fi + verify connection status
- Show device status
- Keyboard relay to compose field

## Deferred (post-MVP)

- Firmware/OS update orchestration
- Log streaming/export bundle
- Multi-device fleet view
- Background notification relays

## Suggested API/BLE contract alignment

- Treat BLE GATT characteristics as source of truth for provisioning and status.
- Keep JSON payload schema versioned (`schema_version`) in request/response bodies.
- Companion should gracefully handle unknown fields for forward compatibility.

## Acceptance criteria

- Fresh device can be provisioned to Wi-Fi from companion app in <3 minutes.
- Invalid tokens never mutate device state.
- Keyboard relay only affects active compose-capable screen.
- Pairing mode timeout auto-reverts discoverability within configured window.
