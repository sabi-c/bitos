# ADR-0001: Adapter contracts + durable outbound queue baseline

- Status: accepted
- Date: 2026-03-14

## Context

Phase 3 requires domain integrations (tasks/messages/email/calendar) without coupling UI code to any single provider/runtime.
We also need resilient outbound write behavior when providers are unavailable.

## Decision

1. Define provider-facing integration points as protocol contracts (`TaskAdapter`, `MessageAdapter`, `EmailAdapter`, `CalendarAdapter`) with a normalized `AdapterResult`.
2. Introduce a local SQLite-backed outbound command queue with explicit states:
   - `pending`
   - `processing`
   - `retrying`
   - `succeeded`
   - `dead_letter`
3. Use bounded retries (`max_attempts`) and delayed retries (`next_attempt_at`) for retryable failures.
4. Persist concise `last_error` text for operator/debug visibility and expose queue metrics (depth, retries, dead letters).

## Rationale (best-practice alignment)

- **Ports-and-adapters pattern:** Keep UI and domain logic independent of concrete providers.
- **At-least-once delivery semantics:** A durable queue with retry supports eventual completion during transient outages.
- **Dead-letter pattern:** Non-retryable or exhausted commands remain inspectable instead of being dropped.
- **Operational visibility:** Lightweight metrics reduce debugging time and improve reliability iteration.

## Consequences

- Provider implementations can be swapped without changing panel/UI code.
- Command processing workers can be added incrementally using the same queue API.
- Idempotency keys may be added in a future ADR to reduce duplicate writes under retry.
