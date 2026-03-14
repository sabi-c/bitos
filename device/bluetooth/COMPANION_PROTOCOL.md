# BITOS BLE Companion Protocol

This is the contract for the companion app (iOS/Android/PWA).

## Connection flow
1. Scan for service UUID: b1705000-0000-4000-8000-000000000001
2. Connect
3. Read AUTH_CHALLENGE
4. Compute HMAC (see auth spec)
5. Write AUTH_RESPONSE
6. Receive session token in AUTH_RESPONSE read-back
7. Subscribe to DEVICE_STATUS notify
8. All subsequent writes include session_token field

## WiFi provisioning
1. Read AUTH_CHALLENGE → authenticate → get session_token
2. Encrypt WiFi password: AES-128-GCM
   key = HKDF(session_token + ble_secret_hint, "wifi-key", 16)
   Note: companion app derives key using the shared secret
   established during pairing (stored by companion after pairing)
3. Write WIFI_CONFIG with encrypted payload
4. Subscribe to WIFI_STATUS for result

## Keyboard input
1. Ensure authenticated (session_token valid)
2. Read DEVICE_STATUS to check active_screen
3. Write KEYBOARD_INPUT with target + text

## Device status monitoring
Subscribe to DEVICE_STATUS characteristic.
Receive JSON updates every 30s or on state change.
