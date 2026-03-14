# BITOS Test Coverage Audit

Scope: `tests/` mapped against current risk areas in `device/`, `server/`, and `companion/` references.

## Findings

| Area | Severity | Gap | Recommendation |
|---|---|---|---|
| WiFi command timeout handling (`device/bluetooth/wifi_manager.py`) | HIGH | No focused tests validate timeout handling or command hang recovery for real-mode subprocess calls. | Add unit tests that mock `subprocess.run` timeout and non-zero exits for all WiFi manager command paths. |
| Render-path I/O contract (`device/overlays/notification.py`, `device/screens/panels/settings.py`) | HIGH | No regression tests enforce that render loops avoid repository reads. | Add tests that instrument repository access and assert zero storage reads during `render()`. |
| Runtime logging behavior (`device/main.py`, `device/input/handler.py`) | MED | Existing tests do not verify logging pathways for error and queue-status output. | Add tests asserting logging calls for button callback errors and queue retry/dead-letter events. |
| BLE pairing responsiveness (`device/bluetooth/server.py`) | MED | No test covers thread stop responsiveness for pairing timer loops. | Add timing-safe tests for stop/shutdown behavior when the pairing thread is active. |
| Companion PWA coverage | MED | No JS/HTML test report is available for `companion/`. | Add baseline lint/unit checks for companion scripts and include report artifact in `docs/reports/`. |

## Summary
- Highest-risk missing tests are concentrated in BLE timeout/recovery and UI render-path performance contracts.
- Priority should be to add deterministic unit tests for timeout and no-I/O-in-render behaviors.
