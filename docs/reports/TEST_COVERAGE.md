## Summary
Overall coverage: 69.2%

Coverage command requested in task could not run because `pytest-cov` is unavailable in this environment (install blocked by proxy). As fallback, coverage was computed by running the full suite with Python's `trace` module and summarizing `device/` + `server/` modules only.

## Untested modules (0% coverage)
- `device/__init__.py`
- `device/audio/__init__.py`
- `device/audio/pipeline.py`
- `device/bluetooth/pairing_agent.py`
- `device/input/__init__.py`
- `device/input/handler.py`
- `device/main.py`
- `device/screens/subscreens/__init__.py`
- `server/__init__.py`

## Low coverage modules (<50%)
- `device/bluetooth/wifi_manager.py` — **18%** — most important untested function: `WiFiManager.add_or_update_network`.
- `device/bluetooth/crypto.py` — **25%** — most important untested function: `_hkdf_sha256`.
- `device/client/api.py` — **44%** — most important untested function: `BackendClient.chat` (error/exception paths).
- `device/display/driver.py` — **44%** — most important untested function: `PygameDriver.present` (and frame lifecycle).
- `device/screens/panels/chat.py` — **47%** — most important untested function: `ChatPanel.handle_action`.
- `device/screens/panels/notifications.py` — **47%** — most important untested function: `NotificationsPanel.handle_action`.
- `device/screens/panels/settings.py` — **47%** — most important untested function: `SettingsPanel.handle_action`.

## Priority test targets
Top 10 functions/classes most worth testing next (ranked by safety-critical behavior, frequent runtime use, and zero-coverage bias):

1. `device/main.py::main` — app bootstrap and main render/input loop (high frequency + currently 0%).
2. `device/input/handler.py::ButtonHandler` — physical input gesture decoding used continuously (0%).
3. `device/bluetooth/pairing_agent.py::BitosPairingAgent` / `MockPairingAgent` — pairing confirmation/auth flow (0%, security-sensitive).
4. `device/bluetooth/wifi_manager.py::WiFiManager.add_or_update_network` — writes Wi-Fi credentials + connection priority.
5. `device/client/api.py::BackendClient.chat` — auth/network timeout handling on primary user write path.
6. `device/screens/panels/settings.py::SettingsPanel.handle_action` — settings changes and persistence-triggering UI paths.
7. `device/screens/panels/chat.py::ChatPanel.handle_action` — high-frequency chat submission/retry actions.
8. `device/bluetooth/crypto.py::decrypt_wifi_password` and `_hkdf_sha256` — credential decryption/key derivation correctness.
9. `device/display/driver.py::PygameDriver` render/present lifecycle — frame stability and display correctness.
10. `device/audio/pipeline.py::AudioPipeline` API contract/error behavior — currently 0% and upstream integration boundary.
