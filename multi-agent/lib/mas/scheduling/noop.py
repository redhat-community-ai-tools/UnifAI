"""
NoOp schedule engine — stand-in when no scheduling infrastructure is configured.

Mirrors the pattern used by ``NoOpTracingService``.  The ``create_schedule``
and ``trigger_now`` methods fail loudly so the user gets immediate feedback
that scheduling is unavailable.  Other methods are silent no-ops because they
may be called against stale data that was persisted before the engine changed.
"""
from typing import Dict, FrozenSet, List, Optional

from mas.scheduling.models import WorkflowSchedule
from mas.scheduling.ports import (
    BatchDescribeResult,
    ScheduleEngine,
    ScheduleInfo,
    ScheduleNotFoundError,
    ScheduleValidationError,
)


class NoOpScheduleEngine(ScheduleEngine):
    """Zero-overhead stand-in when no scheduling engine is available.

    Temporal is currently the only production engine.  When running with
    a local engine (e.g. LangGraph ForegroundRunner), this adapter is
    injected so the system doesn't crash — but it makes clear that
    schedule creation is unsupported.
    """

    def create_schedule(self, schedule: WorkflowSchedule) -> str:
        raise ScheduleValidationError(
            "Workflow scheduling is not available — no engine configured. "
            "Scheduling requires a Temporal backend."
        )

    def pause(self, engine_handle: str) -> None:
        pass

    def resume(self, engine_handle: str) -> None:
        pass

    def delete(self, engine_handle: str) -> None:
        pass

    def update_schedule(self, engine_handle: str, schedule: WorkflowSchedule) -> None:
        pass

    def trigger_now(self, engine_handle: str) -> None:
        raise ScheduleValidationError(
            "Trigger is not available — no scheduling engine configured. "
            "Scheduling requires a Temporal backend."
        )

    def describe(self, engine_handle: str) -> ScheduleInfo:
        raise ScheduleNotFoundError(engine_handle)

    def describe_batch(self, engine_handles: List[str]) -> BatchDescribeResult:
        return BatchDescribeResult(
            found={h: None for h in engine_handles},
            errored=frozenset(),
        )
