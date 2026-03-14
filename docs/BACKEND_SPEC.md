# BITOS Backend API Specification

## Overview

FastAPI backend providing chat streaming, health checks, settings catalog, and provider-agnostic model bridge behavior for BITOS clients.

## Auth model

Device-origin requests use:

1. `X-Device-Token` static identifier token.
2. Request signing header(s) with HMAC over method/path/body/timestamp/nonce.

Backend rejects stale timestamps and nonce reuse.

## Endpoints (current)

### `GET /health`

- Purpose: lightweight service health probe.
- Response: status + runtime/provider metadata safe for UI diagnostics.

### `POST /chat`

- Purpose: stream assistant output for user prompts.
- Input: prompt/session metadata payload.
- Output: SSE stream chunks and terminal completion/error event.

### `GET /settings/catalog`

- Purpose: backend-defined editable UI settings schema.
- Output: fields, defaults, constraints, and display metadata.

### `GET /settings/ui`

- Purpose: current effective UI settings values.

### `PUT /settings/ui`

- Purpose: update persisted UI settings values.
- Behavior: validate and persist atomic update.

## Provider abstraction

`LLM_PROVIDER` determines runtime bridge implementation (`anthropic`, `openai`, `openclaw`, `nanoclaw`, `echo`).

The device/UI must not require provider-specific logic.

## Error contract

- JSON error envelope with stable code identifiers.
- Distinguish retryable transient failures from hard validation failures.
- Preserve concise user-facing message compatibility for tiny-screen UI.

## Operational constraints

- Keep chat stream non-blocking for device render loop.
- Ensure deterministic behavior for local simulator/dev environments.
- Log enough structured diagnostics for outage triage without exposing secrets.
