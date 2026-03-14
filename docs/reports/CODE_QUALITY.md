# BITOS Code Quality Audit Report

Scope reviewed: `device/**/*.py` and `server/**/*.py` after reading `docs/planning/TASK_TRACKER.md` and `README.md`.

## Issues

| File:Line | Category | Severity | Description | Suggested fix |
|---|---|---|---|---|
| `device/overlays/notification.py:97` | ARCH | HIGH | `NotificationShade.render()` performs `self._queue.get_all()` which can trigger DB-backed repository reads on every frame. | Move notification fetch/hydration into update/input flow and render from cached in-memory state. |
| `device/screens/panels/settings.py:90` | ARCH | HIGH | `SettingsPanel.render()` reads persisted settings (`get_setting`) each frame, introducing storage I/O in the render path. | Refresh settings in `update()` or on screen-entry and render only preloaded values. |
| `device/main.py:52` | ARCH | MED | Device runtime uses `print()` for operational logs instead of the logging framework. | Replace all `print()` calls with `logging` and configure handlers/levels centrally. |
| `device/input/handler.py:50` | ARCH | LOW | Button callback exceptions are surfaced via `print()` instead of structured logging with traceback support. | Use `logging.exception()` (or `logging.error(..., exc_info=True)`) for callback error reporting. |
| `device/screens/panels/settings.py:205` | ARCH | LOW | Agent mode options are hardcoded in UI code (`OPTIONS`) instead of sourced from repository-backed settings/configuration. | Persist option catalog in repository/settings config and load it into the panel at initialization. |
| `device/overlays/notification.py:53` | PERF | MED | `pygame.font.Font()` is instantiated in `NotificationToast.render()`, causing repeated font construction in hot render loops. | Cache font objects at overlay construction/startup and reuse cached handles during rendering. |
| `device/bluetooth/server.py:82` | PERF | MED | The pairing countdown thread uses `time.sleep(0.2)` rather than event-driven waiting. | Replace with `threading.Event.wait(timeout)` to improve stop responsiveness and coordination. |
| `device/bluetooth/wifi_manager.py:52` | PERF | HIGH | `subprocess.run()` (`nmcli connection add`) is blocking without timeout and can hang indefinitely. | Add `timeout=` and handle `subprocess.TimeoutExpired` with safe error status. |
| `device/bluetooth/wifi_manager.py:57` | PERF | HIGH | `subprocess.run()` (`nmcli connection up`) has no timeout and can stall connection flow. | Add bounded timeout and map timeout to retryable status output. |
| `device/bluetooth/wifi_manager.py:70` | PERF | HIGH | `subprocess.run()` for active connection status lacks timeout protection. | Add short timeout and fallback status when command execution exceeds budget. |
| `device/bluetooth/wifi_manager.py:84` | PERF | MED | `subprocess.run()` for `hostname -I` has no timeout, allowing potential blocking reads. | Add timeout and return empty/default IP data when timeout occurs. |
| `device/audio/pipeline.py:5` | DEAD_CODE | LOW | `platform` is imported but not referenced anywhere in the module. | Remove the unused import. |
| `device/bluetooth/crypto.py:6` | DEAD_CODE | LOW | `pbkdf2_hmac` direct import is unused. | Delete the unused direct import and keep only required symbols. |
| `device/bluetooth/characteristics/device_status.py:6` | DEAD_CODE | LOW | `time` is imported but never used. | Remove the unused import. |
| `device/display/driver.py:7` | DEAD_CODE | LOW | `sys` is imported but never used. | Remove the unused import. |
| `device/display/animator.py:6` | DEAD_CODE | LOW | `time` is imported but unused by animator functions/classes. | Remove the unused import. |
| `device/bluetooth/wifi_manager.py:40` | MISSING_TEST | MED | WiFi manager logic lacks targeted unit tests for real-mode timeout and command-failure branches. | Add tests that mock `subprocess.run` for timeout/non-zero return cases and assert returned status behavior. |
| `device/overlays/notification.py:96` | MISSING_TEST | LOW | Notification shade behavior is not explicitly guarded by tests for “no repository reads during render” architecture expectations. | Add a regression test that asserts render uses cached records rather than invoking repository fetches. |

## SUMMARY

- Total by severity: **5 HIGH, 5 MED, 8 LOW**
- Top 3 most important fixes:
  1. Remove storage access from render hot paths (`device/overlays/notification.py`, `device/screens/panels/settings.py`).
  2. Add timeouts to all blocking WiFi manager subprocess calls (`device/bluetooth/wifi_manager.py`).
  3. Replace runtime `print()` logging with structured logging (`device/main.py`, `device/input/handler.py`).
