# BITOS Architecture Index

Date: 2026-03-14  
Task: FIX-DOCS-001

This index maps major runtime surfaces to their implementation entry points so audits and future planning checks can reference concrete code locations quickly.

## Preview/UI flow

- Web preview bootstrap and route wiring: `web_preview/server.py`
- Primary callback handoff to home route (preview): `on_home` in `web_preview/server.py`

## Device UI layers (reference)

- Screen orchestration: `device/screens/manager.py`
- Overlay primitives: `device/overlays/`
- Display driver interfaces and implementations: `device/display/`

## Bluetooth/network layers (reference)

- BLE server and pairing surfaces: `device/bluetooth/server.py`, `device/bluetooth/pairing_agent.py`
- BLE auth + characteristics: `device/bluetooth/auth.py`, `device/bluetooth/characteristics/`
- WiFi provisioning runtime: `device/bluetooth/wifi_manager.py`

## Server/backend layers (reference)

- API entrypoint and middleware: `server/main.py`
- LLM provider bridge: `server/llm_bridge.py`
- Config/runtime settings: `server/config.py`, `server/ui_settings.py`

## Logging standard source of truth

- Required startup JSON logging pattern: `docs/planning/DEVELOPMENT_PRACTICES.md` (Section 3)

