# ARCH_CONSISTENCY Audit Report

Date: 2026-03-14
Scope: `docs/planning/SECURITY_DECISIONS.md`, `docs/planning/DEVELOPMENT_PRACTICES.md`, code under `device/`, `server/`, `web_preview/`.

> Note: `docs/BACKEND_SPEC.md` and `docs/BLUETOOTH_NETWORK_SPEC.md` were requested inputs but are currently missing from the repository.

## CHECK 1 — SD number references (`# SD-00X`)

| Finding | File + line | Severity | Fix |
|---|---|---:|---|
| Device-token auth gate has no SD reference comment. | `server/main.py:27-43` | High | Add `# SD-004` near middleware enforcement. |
| Device token secret load has no SD reference comment. | `device/client/api.py:29-37` | High | Add `# SD-004` / `# SD-005` near env reads and header assembly. |
| BLE auth manager loads BLE secret and enforces lockout/session validation without SD comment. | `device/bluetooth/auth.py:25-91` | High | Add `# SD-002` and `# SD-005` comments at secret load and auth checks. |
| Protected BLE WiFi write validates session token but lacks SD comment. | `device/bluetooth/characteristics/wifi_config.py:45-47` | High | Add `# SD-002` on token validation gate. |
| WiFi password decrypt path uses BLE secret without SD comment. | `device/bluetooth/characteristics/wifi_config.py:59-60` | High | Add `# SD-003` and `# SD-005` comments. |
| Protected BLE keyboard write validates session token but lacks SD comment. | `device/bluetooth/characteristics/keyboard_input.py:19-21` | Medium | Add `# SD-002` at validation gate. |
| Outbound permission confirmation gate lacks SD reference. | `device/integrations/permissions.py:27-31` | Medium | Add SD comment documenting confirmation policy linkage. |
| Device startup loads PIN hash / BLE secret with no SD references. | `device/main.py:66-70` | High | Add `# SD-002`/`# SD-005` comments near env reads. |

## CHECK 2 — Environment detection + mock fallback for hardware calls

| Finding | File + line | Severity | Fix |
|---|---|---:|---|
| Audio pipeline does not read `BITOS_AUDIO`; hardware mode selection contract missing. | `device/audio/pipeline.py:15-35` | High | Gate runtime on `BITOS_AUDIO` and keep explicit mock path (`mock`/desktop) with no-op behavior. |
| BLE GATT server hardware branch uses `BITOS_BLUETOOTH` (not one of required env selectors), so it does not follow `BITOS_DISPLAY/BITOS_AUDIO/BITOS_WIFI` contract. | `device/bluetooth/server.py:130-133` | Medium | Align env contract (documented selector or mapped fallback) and keep mock path. |
| Pairing agent hardware path relies on dbus availability only (no env selector). | `device/bluetooth/pairing_agent.py:6-13,19-45` | Medium | Add explicit environment gating for mock vs hardware to match environment-contract policy. |

## CHECK 3 — Callback naming (`on_unlock` occurrences should be zero)

| Finding | File + line | Severity | Fix |
|---|---|---:|---|
| `on_unlock` callback still used in preview flow (5 occurrences). | `web_preview/server.py:119,122,128,149,161` | Medium | Rename callback to approved naming (e.g., `on_unlock_complete`/`go_home`) and update call sites. |

## CHECK 4 — Planning docs vs code alignment

### 4A) Classes mentioned in planning docs that do not exist in code

| Finding | File + line | Severity | Fix |
|---|---|---:|---|
| `JsonFormatter` is specified in development-practices logging example but no production class exists. | `docs/planning/DEVELOPMENT_PRACTICES.md:154` | Low | Either implement shared `JsonFormatter` utility or mark snippet as illustrative only. |

### 4B) Classes in code not mentioned anywhere in docs

| Finding | File + line | Severity | Fix |
|---|---|---:|---|
| The following 45 classes are currently undocumented in `docs/**/*.md`: `PasskeyOverlay`, `NotificationRecord`, `NotificationShade`, `NotificationQueue`, `ButtonEvent`, `ButtonHandler`, `NotificationPoller`, `LockScreen`, `BootScreen`, `NotificationsPanel`, `SettingsPanel`, `ModelPickerPanel`, `AgentModePanel`, `SleepTimerPanel`, `AboutPanel`, `EmailComposeSubscreen`, `SMSComposeSubscreen`, `BackendChatError`, `AudioPipeline`, `DisplayDriver`, `ST7789Driver`, `WiFiManager`, `MockPairingAgent`, `BitosGATTServer`, `MockGATTServer`, `AuthError`, `AuthResponseCharacteristic`, `DeviceStatusCharacteristic`, `WiFiStatusCharacteristic`, `WiFiConfigCharacteristic`, `AuthChallengeCharacteristic`, `KeyboardInputCharacteristic`, `OutboundWorkerRuntimeLoop`, `EchoAdapter`, `DisabledAdapter`, `PermissionDeniedError`, `CommandRequest`, `WorkerResult`, `QueuedCommand`, `OutboundCommandQueue`, `UISettingsValidationError`, `UISettingsStore`, `LLMBridge`, `AnthropicBridge`, `EchoBridge`. | Multiple (see class definition sites in code) | Low | Add architecture index pages per subsystem (UI, BLE, integrations, server) and link each class role at least once. |

## Additional repository consistency issue

| Finding | File + line | Severity | Fix |
|---|---|---:|---|
| Required spec files are missing: `docs/BACKEND_SPEC.md`, `docs/BLUETOOTH_NETWORK_SPEC.md`. | `docs/` (missing files) | Medium | Restore or replace these specs, then rerun audit for full parity check. |
