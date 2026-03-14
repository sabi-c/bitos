# BITOS Code Quality Audit Report

Scope reviewed: `device/**/*.py` and `server/**/*.py` after reading `docs/planning/TASK_TRACKER.md` and `README.md`.

## Issues

| File:Line | Category | Severity | Description | Suggested fix |
|---|---|---|---|---|
| `device/overlays/notification.py:97` | ARCH | HIGH | `NotificationShade.render()` performs `self._queue.get_all()` which can trigger a repository read on every frame. | Move notification record hydration to update/input paths (or cache snapshot state) so `render()` only draws pre-fetched data. |
| `device/overlays/notification.py:53` | PERF | MED | `pygame.font.Font()` is instantiated from `NotificationToast.render()` which can repeatedly allocate font resources during rendering. | Initialize and cache font objects during overlay setup/startup and reuse them in render loops. |
| `device/main.py:52` | ARCH | MED | The runtime emits direct `print()` output instead of using the logging stack. | Replace `print()` calls with structured `logging` calls and configure log level/handlers centrally. |
| `device/input/handler.py:50` | ARCH | LOW | Button callback errors are reported via `print()` instead of project logging conventions. | Swap `print()` for `logging.exception()` (or `logging.error(..., exc_info=True)`) to preserve stack traces consistently. |
| `device/bluetooth/server.py:82` | PERF | MED | The pairing countdown loop uses `time.sleep(0.2)` rather than event-driven waiting, reducing thread responsiveness. | Use `threading.Event.wait(timeout)` with an interrupt event to coordinate cancellation and sleep behavior. |
| `device/bluetooth/wifi_manager.py:52` | PERF | HIGH | `subprocess.run()` for `nmcli connection add` has no timeout, so the worker can block indefinitely. | Add explicit `timeout=` and handle `TimeoutExpired` for safe failure behavior. |
| `device/bluetooth/wifi_manager.py:57` | PERF | HIGH | `subprocess.run()` for `nmcli connection up` has no timeout, so connection attempts may hang the caller. | Add explicit `timeout=` and map timeout failures to a clean retryable error/status. |
| `device/bluetooth/wifi_manager.py:70` | PERF | HIGH | `subprocess.run()` for active connection status uses no timeout and may block runtime status polling. | Add a short timeout and graceful fallback status when command execution exceeds budget. |
| `device/bluetooth/wifi_manager.py:84` | PERF | MED | `subprocess.run()` for `hostname -I` is blocking without timeout. | Add timeout protection and return a safe default when IP lookup times out. |
| `device/audio/pipeline.py:5` | DEAD_CODE | LOW | `platform` is imported but never used. | Remove the unused import to reduce noise and maintenance overhead. |
| `device/bluetooth/crypto.py:6` | DEAD_CODE | LOW | `pbkdf2_hmac` is imported directly but never referenced. | Remove the unused direct import and keep only actively used symbols. |
| `device/bluetooth/characteristics/device_status.py:6` | DEAD_CODE | LOW | `time` is imported but unused in the module. | Delete the unused import. |
| `device/display/driver.py:7` | DEAD_CODE | LOW | `sys` is imported but never used. | Remove the unused import. |
| `device/display/animator.py:6` | DEAD_CODE | LOW | `time` is imported but never used by animator helpers. | Remove the unused import. |
| `tests/test_wifi_config.py:83` | MISSING_TEST | MED | Existing WiFi manager tests validate mock mode only and do not cover timeout/error paths for real `nmcli` subprocess calls. | Add unit tests that mock `subprocess.run` timeout/return-code behavior to lock down non-blocking failure handling. |

## SUMMARY

- Total by severity: **4 HIGH, 4 MED, 7 LOW**
- Top 3 most important fixes:
  1. Remove DB access from `NotificationShade.render()` hot path (`device/overlays/notification.py:97`).
  2. Add timeouts to all `subprocess.run()` calls in WiFi manager (`device/bluetooth/wifi_manager.py`).
  3. Replace runtime `print()` statements with structured logging (`device/main.py`, `device/input/handler.py`).
