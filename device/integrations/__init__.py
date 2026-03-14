"""Integration contracts, queue primitives, and outbound processing services."""

from .contracts import AdapterResult, CalendarAdapter, EmailAdapter, MessageAdapter, TaskAdapter
from .permissions import CommandRequest, OutboundCommandService, PermissionDeniedError
from .queue import OutboundCommandQueue, QueuedCommand
from .worker import OutboundCommandWorker, WorkerResult

__all__ = [
    "AdapterResult",
    "TaskAdapter",
    "MessageAdapter",
    "EmailAdapter",
    "CalendarAdapter",
    "PermissionDeniedError",
    "CommandRequest",
    "OutboundCommandService",
    "OutboundCommandQueue",
    "QueuedCommand",
    "OutboundCommandWorker",
    "WorkerResult",
]
