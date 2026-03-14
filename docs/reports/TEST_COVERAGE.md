## Summary
Overall coverage: 69.2%

_Source: fallback `trace`-based run over the full test suite (`109 passed, 2 skipped`) because `pytest-cov` could not be installed in this environment._

## Untested modules (0% coverage)
- `device/audio/pipeline.py`
- `device/bluetooth/pairing_agent.py`
- `device/input/handler.py`
- `device/main.py`
- `device/screens/subscreens/__init__.py`
- `device/__init__.py`
- `device/audio/__init__.py`
- `device/input/__init__.py`
- `server/__init__.py`

## Low coverage modules (<50%)
- `device/bluetooth/crypto.py` — **25%** — most important untested function: `_hkdf_sha256`.
- `device/bluetooth/wifi_manager.py` — **18%** — most important untested function: `WiFiManager.add_or_update_network`.
- `device/client/api.py` — **44%** — most important untested function: `BackendClient.chat` error-path handling (timeouts/auth/rate limit).
- `device/display/driver.py` — **44%** — most important untested function: `PygameDriver` render/display lifecycle methods.
- `device/screens/panels/chat.py` — **47%** — most important untested function: `ChatPanel` submit/retry/status flow.
- `device/screens/panels/notifications.py` — **47%** — most important untested function: `NotificationsPanel` action/input transitions.
- `device/screens/panels/settings.py` — **47%** — most important untested function: `SettingsPanel` model/agent/sleep/about routing + persistence interactions.

## Priority test targets
Top 10 functions/classes to test next (ordered by safety-critical impact, frequency of execution, and current coverage gaps):

1. `device/main.py::main` (0%) — runtime bootstrap + loop wiring, service startup/shutdown paths.
2. `device/input/handler.py::ButtonHandler` (0%) — core input gesture decoding used every frame.
3. `device/bluetooth/pairing_agent.py::MockPairingAgent` and DBus agent callbacks (0%) — pairing/auth handshake path.
4. `device/bluetooth/wifi_manager.py::WiFiManager.add_or_update_network` (18%) — writes network credentials and connection priority.
5. `device/client/api.py::BackendClient.chat` (44%) — auth/permission/network failure handling for user-visible chat writes.
6. `device/screens/panels/settings.py::SettingsPanel` interaction handlers (47%) — settings writes and navigation logic.
7. `device/screens/panels/chat.py::ChatPanel` send/retry handlers (47%) — primary high-frequency user path.
8. `device/bluetooth/crypto.py::decrypt_wifi_password` + `_hkdf_sha256` (25%) — credential decryption and key derivation correctness.
9. `device/display/driver.py::PygameDriver` frame/update methods (44%) — render loop stability and frame presentation.
10. `device/audio/pipeline.py::AudioPipeline` stubs/error contracts (0%) — currently unexercised API boundary.
