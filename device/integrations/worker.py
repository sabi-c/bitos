"""Outbound command queue worker that dispatches to domain adapters."""
from __future__ import annotations

import json
from dataclasses import dataclass

from .contracts import AdapterResult, CalendarAdapter, EmailAdapter, MessageAdapter, TaskAdapter
from .queue import OutboundCommandQueue


@dataclass(frozen=True)
class WorkerResult:
    command_id: int
    status: str
    reason: str | None = None


class OutboundCommandWorker:
    """Processes ready queue items using adapter contracts only."""

    def __init__(
        self,
        queue: OutboundCommandQueue,
        task_adapter: TaskAdapter | None = None,
        message_adapter: MessageAdapter | None = None,
        email_adapter: EmailAdapter | None = None,
        calendar_adapter: CalendarAdapter | None = None,
        default_backoff_seconds: float = 2.0,
    ):
        self.queue = queue
        self.task_adapter = task_adapter
        self.message_adapter = message_adapter
        self.email_adapter = email_adapter
        self.calendar_adapter = calendar_adapter
        self.default_backoff_seconds = default_backoff_seconds

    def process_once(self, now: float | None = None) -> WorkerResult | None:
        command = self.queue.reserve_next_ready(now=now)
        if command is None:
            return None

        try:
            payload = json.loads(command.payload)
        except json.JSONDecodeError:
            self.queue.mark_failed(command.id, reason="invalid_payload", retryable=False)
            return WorkerResult(command_id=command.id, status="dead_letter", reason="invalid_payload")

        result = self._dispatch(command.domain, command.operation, payload)
        if result.success:
            self.queue.mark_succeeded(command.id)
            return WorkerResult(command_id=command.id, status="succeeded")

        status = self.queue.mark_failed(
            command.id,
            reason=result.reason or "adapter_failure",
            retryable=result.retryable,
            backoff_seconds=self.default_backoff_seconds,
        )
        return WorkerResult(command_id=command.id, status=status, reason=result.reason)

    def _dispatch(self, domain: str, operation: str, payload: dict) -> AdapterResult:
        try:
            if domain == "task":
                if self.task_adapter is None:
                    return AdapterResult(success=False, reason="adapter_unavailable", retryable=True)
                if operation == "create":
                    return self.task_adapter.create_task(
                        title=str(payload["title"]),
                        details=payload.get("details"),
                    )
                if operation == "complete":
                    return self.task_adapter.complete_task(str(payload["provider_task_id"]))

            if domain == "message":
                if self.message_adapter is None:
                    return AdapterResult(success=False, reason="adapter_unavailable", retryable=True)
                if operation == "send":
                    return self.message_adapter.send_message(
                        recipient=str(payload["recipient"]),
                        body=str(payload["body"]),
                    )

            if domain == "email":
                if self.email_adapter is None:
                    return AdapterResult(success=False, reason="adapter_unavailable", retryable=True)
                if operation == "send":
                    return self.email_adapter.send_email(
                        recipient=str(payload["recipient"]),
                        subject=str(payload["subject"]),
                        body=str(payload["body"]),
                    )

            if domain == "calendar":
                if self.calendar_adapter is None:
                    return AdapterResult(success=False, reason="adapter_unavailable", retryable=True)
                if operation == "create_event":
                    return self.calendar_adapter.create_event(
                        title=str(payload["title"]),
                        starts_at_iso=str(payload["starts_at_iso"]),
                        ends_at_iso=str(payload["ends_at_iso"]),
                    )
        except (KeyError, TypeError, ValueError):
            return AdapterResult(success=False, reason="invalid_payload", retryable=False)

        return AdapterResult(success=False, reason="unsupported_operation", retryable=False)
