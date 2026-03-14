# MASTER AUDIT SUMMARY

## Critical issues (must fix before hardware deploy)
- **[BLE]** Add timeouts for `nmcli connection add` in `device/bluetooth/wifi_manager.py` to prevent indefinite blocking in provisioning flows.
- **[BLE]** Add timeouts for `nmcli connection up` in `device/bluetooth/wifi_manager.py` to avoid hangs while joining networks.
- **[BLE]** Add timeout protection for active-connection status checks in `device/bluetooth/wifi_manager.py`.
- **[UI]** Remove DB-backed reads from `NotificationShade.render()` in `device/overlays/notification.py` to keep render loops non-blocking.
- **[UI]** Remove repository reads from `SettingsPanel.render()` in `device/screens/panels/settings.py` and render from cached state.

## Recommended next sprint fixes
1. **[BLE]** Implement explicit subprocess timeouts + `TimeoutExpired` handling for all WiFi manager commands.
2. **[BLE]** Add unit tests for WiFi manager timeout, non-zero return-code, and recovery paths.
3. **[UI]** Refactor NotificationShade to hydrate records in update/input lifecycle and render cached records only.
4. **[UI]** Add regression test to enforce “no repository reads in render” for notification shade.
5. **[UI]** Refactor SettingsPanel to refresh settings on enter/update rather than per-frame calls.
6. **[UI]** Cache overlay fonts at construction/startup instead of creating `pygame.font.Font()` during render.
7. **[DOCS]** Replace runtime `print()` statements with structured logging guidance and align implementation to it.
8. **[BLE]** Replace pairing-thread `time.sleep()` loop with `threading.Event.wait()` for better stop responsiveness.
9. **[UI]** Move hardcoded agent-mode options into repository-backed settings/catalog config.
10. **[DOCS]** Re-run and publish the missing audit artifacts: `TEST_COVERAGE.md`, `DEPENDENCY_AUDIT.md`, `ARCH_CONSISTENCY.md`.
11. **[SERVER]** After missing reports are generated, integrate any server-critical findings into this priority list.
12. **[COMPANION]** After missing reports are generated, integrate any companion-critical findings into sprint backlog.

## What's healthy
The audit surfaced concrete, file-level findings with actionable fixes and clear severity labeling, which makes triage straightforward. The highest-risk items are concentrated in a small set of modules, so remediation can be focused and fast. Existing test infrastructure already covers parts of BLE and notifications, providing a foundation for adding the missing regression cases. Repository organization and task tracking are strong enough to support parallel lanes without major planning overhead.

## Parallel work opportunities
- **UI lane (in parallel):** notification render-path refactor + settings render-path refactor + font-cache optimization (primarily `device/overlays/` and `device/screens/`).
- **BLE lane (in parallel):** WiFi manager timeout hardening + pairing loop wait strategy + WiFi manager tests (primarily `device/bluetooth/` and `tests/`).
- **Cross-cutting docs lane (in parallel with UI/BLE):** logging standards update + regenerate missing audit reports (`docs/reports/`).
- **Deferred lanes pending missing reports:** SERVER and COMPANION prioritization can run independently once those artifacts are produced.
