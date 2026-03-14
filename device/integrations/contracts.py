"""Provider-agnostic domain adapter contracts for external integrations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class AdapterResult:
    """Normalized write-operation result for domain adapters."""

    success: bool
    external_id: str | None = None
    reason: str | None = None
    retryable: bool = False


@runtime_checkable
class TaskAdapter(Protocol):
    def create_task(self, title: str, details: str | None = None) -> AdapterResult:
        """Create a task in the external provider."""

    def complete_task(self, provider_task_id: str) -> AdapterResult:
        """Mark a provider task complete."""


@runtime_checkable
class MessageAdapter(Protocol):
    def send_message(self, recipient: str, body: str) -> AdapterResult:
        """Send an outbound message."""


@runtime_checkable
class EmailAdapter(Protocol):
    def send_email(self, recipient: str, subject: str, body: str) -> AdapterResult:
        """Send an outbound email."""


@runtime_checkable
class CalendarAdapter(Protocol):
    def create_event(self, title: str, starts_at_iso: str, ends_at_iso: str) -> AdapterResult:
        """Create a calendar event."""
