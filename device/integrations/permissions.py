"""Permission/confirmation gate for outbound write operations."""
from __future__ import annotations

from dataclasses import dataclass

from .queue import OutboundCommandQueue


class PermissionDeniedError(ValueError):
    """Raised when a write action is not explicitly confirmed."""


@dataclass(frozen=True)
class CommandRequest:
    domain: str
    operation: str
    payload: str
    max_attempts: int = 3
    confirmed: bool = False


class OutboundCommandService:
    """Gates write actions behind explicit confirmation before enqueuing."""

    def __init__(self, queue: OutboundCommandQueue):
        self.queue = queue

    def submit(self, request: CommandRequest) -> int:
        if not request.confirmed:
            raise PermissionDeniedError(
                f"Outbound write '{request.domain}.{request.operation}' requires explicit confirmation"
            )
        return self.queue.enqueue(
            domain=request.domain,
            operation=request.operation,
            payload=request.payload,
            max_attempts=request.max_attempts,
        )
