# ADR-0002: Explicit permission gate + adapter-driven queue worker

- Status: accepted
- Date: 2026-03-14

## Context

After adding adapter contracts and durable queue persistence, Phase 3 still needed:
- explicit confirmation before write actions are persisted/executed
- a worker path that drains queued commands without leaking provider logic into UI/panels

## Decision

1. Add `OutboundCommandService` with a strict confirmation gate (`confirmed=True`) before enqueue.
2. Add `OutboundCommandWorker` that:
   - reserves ready items from the queue
   - parses payload JSON
   - dispatches by domain/operation through adapter contracts only
   - marks success/retry/dead-letter based on normalized `AdapterResult`
3. Treat missing adapters as retryable (`adapter_unavailable`) to support staged startup/recovery.
4. Treat malformed/unsupported payloads as non-retryable (`invalid_payload` / `unsupported_operation`).

## Rationale (best-practice alignment)

- **Human-in-the-loop safety:** explicit write confirmation reduces accidental outbound side effects.
- **Separation of concerns:** queue worker depends on contracts, not concrete providers.
- **Resilience:** retry for transient infrastructure issues, dead-letter for deterministic failures.
- **Testability:** worker logic is deterministic with mock adapters + clock-injected `now`.

## Consequences

- UI can call one service API for safe enqueue semantics.
- Background processing can run on device loop or side thread using `process_once()`.
- Future work should add idempotency keys and structured payload schema validation.
