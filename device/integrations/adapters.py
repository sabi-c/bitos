# WHY THIS EXISTS: Provide runtime-selectable local adapter implementations so outbound command wiring can run without external providers.
# INTRODUCED IN: P4-002
# DEPENDED ON BY: device/main.py, tests/test_outbound_runtime_loop.py
"""Runtime-selectable adapter implementations for outbound command domains."""
from __future__ import annotations

import os

from .contracts import AdapterResult, CalendarAdapter, EmailAdapter, MessageAdapter, TaskAdapter


class EchoAdapter(TaskAdapter, MessageAdapter, EmailAdapter, CalendarAdapter):
    """Local deterministic adapter that acknowledges writes for simulator/dev flows."""

    def create_task(self, title: str, details: str | None = None) -> AdapterResult:
        return AdapterResult(success=True, external_id=f"task:{title[:24]}")

    def complete_task(self, provider_task_id: str) -> AdapterResult:
        return AdapterResult(success=True, external_id=provider_task_id)

    def send_message(self, recipient: str, body: str) -> AdapterResult:
        return AdapterResult(success=True, external_id=f"msg:{recipient[:24]}")

    def send_email(self, recipient: str, subject: str, body: str) -> AdapterResult:
        return AdapterResult(success=True, external_id=f"email:{recipient[:24]}")

    def create_event(self, title: str, starts_at_iso: str, ends_at_iso: str) -> AdapterResult:
        return AdapterResult(success=True, external_id=f"event:{title[:24]}")


class DisabledAdapter(TaskAdapter, MessageAdapter, EmailAdapter, CalendarAdapter):
    """Adapter mode that intentionally leaves writes unavailable (retryable)."""

    def _unavailable(self) -> AdapterResult:
        return AdapterResult(success=False, reason="adapter_unavailable", retryable=True)

    def create_task(self, title: str, details: str | None = None) -> AdapterResult:
        return self._unavailable()

    def complete_task(self, provider_task_id: str) -> AdapterResult:
        return self._unavailable()

    def send_message(self, recipient: str, body: str) -> AdapterResult:
        return self._unavailable()

    def send_email(self, recipient: str, subject: str, body: str) -> AdapterResult:
        return self._unavailable()

    def create_event(self, title: str, starts_at_iso: str, ends_at_iso: str) -> AdapterResult:
        return self._unavailable()


def create_runtime_adapter() -> TaskAdapter | MessageAdapter | EmailAdapter | CalendarAdapter:
    """Create adapter implementation from BITOS_ADAPTER_MODE.

    Supported modes:
    - echo (default): deterministic local success adapter.
    - disabled: explicit unavailable adapter (commands retry/dead-letter based on policy).
    """

    mode = os.environ.get("BITOS_ADAPTER_MODE", "echo").strip().lower()
    if mode == "disabled":
        return DisabledAdapter()
    return EchoAdapter()
