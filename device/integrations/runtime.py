# WHY THIS EXISTS: Provide a bounded non-blocking tick loop for outbound queue worker processing from the device runtime.
# INTRODUCED IN: P4-002
# DEPENDED ON BY: device/main.py, tests/test_outbound_runtime_loop.py
"""Non-blocking runtime loop pump for outbound queue processing."""
from __future__ import annotations

import time

from .worker import OutboundCommandWorker, WorkerResult


class OutboundWorkerRuntimeLoop:
    """Processes queued outbound commands in bounded, periodic slices."""

    def __init__(self, worker: OutboundCommandWorker, interval_seconds: float = 0.2, max_per_tick: int = 1):
        self._worker = worker
        self._interval_seconds = max(0.0, interval_seconds)
        self._max_per_tick = max(1, int(max_per_tick))
        self._next_run_at = 0.0

    def tick(self, now: float | None = None) -> list[WorkerResult]:
        current = time.time() if now is None else now
        if current < self._next_run_at:
            return []

        results: list[WorkerResult] = []
        for _ in range(self._max_per_tick):
            result = self._worker.process_once(now=current)
            if result is None:
                break
            results.append(result)

        self._next_run_at = current + self._interval_seconds
        return results
