# MASTER AUDIT SUMMARY

## Critical issues (must fix before hardware deploy)
1. **[BLE]** Add mandatory timeouts and timeout handling for `nmcli connection add` in `device/bluetooth/wifi_manager.py`.
2. **[BLE]** Add mandatory timeouts and timeout handling for `nmcli connection up` in `device/bluetooth/wifi_manager.py`.
3. **[BLE]** Add timeout protection for active network status subprocess calls in `device/bluetooth/wifi_manager.py`.
4. **[UI]** Remove repository reads from `NotificationShade.render()` in `device/overlays/notification.py`.
5. **[UI]** Remove repository reads from `SettingsPanel.render()` in `device/screens/panels/settings.py`.
6. **[BLE]** Close test gap for WiFi manager timeout and command-failure recovery branches.
7. **[UI]** Add regression coverage to enforce no storage I/O in render hot paths.
8. **[SERVER]** Enforce shared timeout policy for outbound HTTP calls to prevent regression in future callsites.

## Recommended next sprint fixes
1. **[BLE]** Implement shared subprocess timeout constants + `TimeoutExpired` handling for all WiFi manager command paths.
2. **[BLE]** Add unit tests for WiFi manager timeout, non-zero exit, and retryable error classification.
3. **[UI]** Refactor NotificationShade to fetch/hydrate data outside render and draw only cached frame-state.
4. **[UI]** Add render-path regression test that fails on repository access during `render()`.
5. **[UI]** Refactor SettingsPanel state loading to on-enter/update lifecycle hooks.
6. **[UI]** Cache `pygame.font.Font()` objects at screen/overlay initialization.
7. **[SERVER]** Add a shared HTTP client helper that enforces standardized timeout defaults.
8. **[DOCS]** Replace runtime `print()` usage guidance with structured logging policy and examples.
9. **[BLE]** Replace pairing loop `time.sleep()` with `threading.Event.wait()` for clean stop semantics.
10. **[UI]** Move hardcoded agent-mode option catalog into repository-backed settings/config.
11. **[COMPANION]** Add baseline companion lint/unit checks and publish a coverage artifact each audit cycle.
12. **[DOCS]** Maintain synchronized quarterly audit artifacts for all four report files.

## What's healthy
The issues are concentrated in a few modules, which makes remediation focused rather than broad. Existing architecture already separates UI, BLE, and server concerns enough to support lane-based execution. Current tests provide a usable base to add high-impact regressions quickly. Task tracking is active and detailed, enabling predictable sequencing and handoff quality.

## Parallel work opportunities
- **UI lane:** render-path purity refactors + font caching + UI regression tests (`device/screens/`, `device/overlays/`, related tests).
- **BLE lane:** subprocess timeout hardening + pairing loop responsiveness + BLE-focused tests (`device/bluetooth/`, related tests).
- **SERVER lane:** shared HTTP timeout helper and timeout policy coverage (`server/`, server tests).
- **COMPANION lane:** baseline lint/unit harness and report publication (`companion/`, docs/report pipeline).
- **DOCS lane:** logging policy updates and recurring audit process documentation (`docs/`).
