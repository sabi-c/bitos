"""Local outbound command queue with retry/dead-letter behavior."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from storage.repository import DeviceRepository


@dataclass(frozen=True)
class QueuedCommand:
    id: int
    domain: str
    operation: str
    payload: str
    status: str
    attempt_count: int
    max_attempts: int
    last_error: str | None
    next_attempt_at: float
    created_at: float
    updated_at: float


class OutboundCommandQueue:
    """High-level queue API over repository-backed command persistence."""

    def __init__(self, repository: DeviceRepository):
        self.repository = repository

    def enqueue(self, domain: str, operation: str, payload: str, max_attempts: int = 3) -> int:
        return self.repository.queue_enqueue_command(
            domain=domain,
            operation=operation,
            payload=payload,
            max_attempts=max_attempts,
        )

    def reserve_next_ready(self, now: float | None = None) -> QueuedCommand | None:
        row = self.repository.queue_reserve_next_ready(now=now or time.time())
        if not row:
            return None
        return QueuedCommand(**row)

    def mark_succeeded(self, command_id: int) -> None:
        self.repository.queue_mark_succeeded(command_id)

    def mark_failed(self, command_id: int, reason: str, retryable: bool, backoff_seconds: float = 2.0) -> str:
        return self.repository.queue_mark_failed(
            command_id=command_id,
            reason=reason,
            retryable=retryable,
            backoff_seconds=backoff_seconds,
        )

    def list_dead_letters(self, limit: int = 25) -> list[QueuedCommand]:
        rows = self.repository.queue_list_dead_letters(limit=limit)
        return [QueuedCommand(**row) for row in rows]

    def metrics(self) -> dict[str, Any]:
        return self.repository.queue_metrics()
