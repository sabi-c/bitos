# ARCH_CONSISTENCY Audit Report

Date: 2026-03-14
Scope: `docs/planning/SECURITY_DECISIONS.md`, `docs/planning/DEVELOPMENT_PRACTICES.md`, and Python code under `device/`, `server/`, `web_preview/`.

> Input file status: requested `docs/BACKEND_SPEC.md` and `docs/BLUETOOTH_NETWORK_SPEC.md` are not present in this repository snapshot.

## CHECK 1 — SD number references (`# SD-00X`)

| Finding | File + line | Severity | Fix |
|---|---|---:|---|
| Missing SD reference on device-token auth middleware path | `server/main.py:27-43` | High | Add # SD-004 on middleware enforcement. |
| Missing SD references where device token secret is loaded and sent | `device/client/api.py:29-37` | High | Add # SD-004/# SD-005 near env-read/header logic. |
| Missing SD references on BLE auth secret/session/lockout flow | `device/bluetooth/auth.py:25-91` | High | Add # SD-002 and # SD-005 comments at relevant gates. |
| Missing SD reference on protected WiFi write session-token gate | `device/bluetooth/characteristics/wifi_config.py:45-47` | High | Add # SD-002 on token validation. |
| Missing SD references on WiFi password decrypt path | `device/bluetooth/characteristics/wifi_config.py:59-60` | High | Add # SD-003/# SD-005 near decrypt and secret use. |
| Missing SD reference on protected keyboard write session-token gate | `device/bluetooth/characteristics/keyboard_input.py:19-21` | Medium | Add # SD-002 on token validation. |
| Missing SD references where PIN hash/BLE secret are loaded at startup | `device/main.py:66-70` | High | Add # SD-002/# SD-005 near env reads. |

## CHECK 2 — Environment detection + mock fallback

| Finding | File + line | Severity | Fix |
|---|---|---:|---|
| Audio pipeline lacks BITOS_AUDIO environment gating despite hardware-contract requirement | `device/audio/pipeline.py:15-35` | High | Read BITOS_AUDIO and keep explicit mock path. |
| BLE server gating is keyed to BITOS_BLUETOOTH, not the required env contract | `device/bluetooth/server.py:130-133` | Medium | Align environment gating contract and keep mock fallback. |
| Pairing agent chooses hardware path only by dbus availability, no explicit env switch | `device/bluetooth/pairing_agent.py:6-13,19-45` | Medium | Add environment-based mock/hardware selector. |

## CHECK 3 — Callback naming (`on_unlock`)

| Finding | File + line | Severity | Fix |
|---|---|---:|---|
| `on_unlock` occurrence found | `web_preview/server.py:119` | Medium | Rename callback to approved convention and update call sites. |
| `on_unlock` occurrence found | `web_preview/server.py:122` | Medium | Rename callback to approved convention and update call sites. |
| `on_unlock` occurrence found | `web_preview/server.py:128` | Medium | Rename callback to approved convention and update call sites. |
| `on_unlock` occurrence found | `web_preview/server.py:149` | Medium | Rename callback to approved convention and update call sites. |
| `on_unlock` occurrence found | `web_preview/server.py:161` | Medium | Rename callback to approved convention and update call sites. |

## CHECK 4 — Planning docs vs code alignment

### 4A) Classes mentioned in planning docs but missing in code

| Finding | File + line | Severity | Fix |
|---|---|---:|---|
| `JsonFormatter` is referenced in planning docs but has no code class definition. | `docs/planning/DEVELOPMENT_PRACTICES.md:154` | Low | Implement class or mark snippet as illustrative only. |

### 4B) Classes in code not mentioned anywhere in docs

| Finding | File + line | Severity | Fix |
|---|---|---:|---|
| None. | n/a | Info | No action required. |

## Additional repository consistency issue

| Finding | File + line | Severity | Fix |
|---|---|---:|---|
| Required audit inputs are missing: `docs/BACKEND_SPEC.md`, `docs/BLUETOOTH_NETWORK_SPEC.md`. | `docs/` | Medium | Restore/add these specs, then rerun this audit for full coverage. |
