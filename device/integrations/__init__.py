"""Integration contracts, queue primitives, and outbound processing services."""

from .contracts import AdapterResult, CalendarAdapter, EmailAdapter, MessageAdapter, TaskAdapter
from .permissions import CommandRequest, OutboundCommandService, PermissionDeniedError
from .queue import OutboundCommandQueue, QueuedCommand
from .worker import OutboundCommandWorker, WorkerResult
from .adapters import EchoAdapter, DisabledAdapter, create_runtime_adapter
from .runtime import OutboundWorkerRuntimeLoop

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
    "EchoAdapter",
    "DisabledAdapter",
    "create_runtime_adapter",
    "OutboundWorkerRuntimeLoop",
]
