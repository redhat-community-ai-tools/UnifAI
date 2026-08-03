"""
Schedule engine port (ABC) -- outbound port for schedule orchestration.

Abstracts the external scheduling API behind a domain port so the
domain never imports any infrastructure library.
"""
from abc import ABC, abstractmethod
from typing import Dict, FrozenSet, List, Optional

from pydantic import BaseModel, Field

from mas.scheduling.models import WorkflowSchedule


class ScheduleEngineError(Exception):
    """Base for all schedule-engine port failures.

    Adapters must translate infrastructure errors into this hierarchy so
    application services never catch bare ``Exception`` around engine calls.
    """


class ScheduleNotFoundError(ScheduleEngineError):
    """Raised when a schedule does not exist in the external orchestrator."""

    def __init__(self, schedule_id: str) -> None:
        self.schedule_id = schedule_id
        super().__init__(f"Schedule not found: {schedule_id}")


class ScheduleDescribeError(ScheduleEngineError):
    """Transient failure while describing a schedule (e.g. RPC timeout)."""

    def __init__(self, schedule_id: str) -> None:
        self.schedule_id = schedule_id
        super().__init__(f"Transient describe failure: {schedule_id}")


class ScheduleValidationError(ScheduleEngineError, ValueError):
    """Raised when the external orchestrator rejects a schedule as malformed.

    Subclasses ValueError so it flows through the same clean 400 handling
    as domain-level validation errors, rather than surfacing as a raw RPC
    failure to callers.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ScheduleInfo(BaseModel):
    """Read-back snapshot of a schedule's live state in the orchestrator."""

    model_config = {"frozen": True}

    paused: bool
    remaining_actions: Optional[int]
    running: bool


class BatchDescribeResult(BaseModel):
    """Result of a batch describe operation.

    ``found`` maps engine handles to their info (None = confirmed not found).
    ``errored`` contains handles whose lookup failed due to transient errors.
    """

    model_config = {"frozen": True}

    found: Dict[str, Optional[ScheduleInfo]] = Field(default_factory=dict)
    errored: FrozenSet[str] = frozenset()


class ScheduleEngine(ABC):
    """Outbound port for schedule timer management.

    Each infrastructure adapter (Temporal Schedules, Celery Beat, …)
    implements this port.
    """

    @abstractmethod
    def create_schedule(self, schedule: WorkflowSchedule) -> str:
        """Create a schedule in the engine. Returns the engine handle."""
        ...

    @abstractmethod
    def pause(self, engine_handle: str) -> None:
        """Pause a running schedule."""
        ...

    @abstractmethod
    def resume(self, engine_handle: str) -> None:
        """Resume a paused schedule."""
        ...

    @abstractmethod
    def delete(self, engine_handle: str) -> None:
        """Delete a schedule permanently."""
        ...

    @abstractmethod
    def update_schedule(self, engine_handle: str, schedule: WorkflowSchedule) -> None:
        """Atomically update an existing schedule in-place."""
        ...

    @abstractmethod
    def trigger_now(self, engine_handle: str) -> None:
        """Trigger an immediate execution of the schedule (one-off)."""
        ...

    @abstractmethod
    def describe(self, engine_handle: str) -> ScheduleInfo:
        """Read-back the schedule's live state from the orchestrator."""
        ...

    def describe_batch(self, engine_handles: List[str]) -> BatchDescribeResult:
        """Batch read-back of multiple schedules' live state.

        Default implementation falls back to sequential describe() calls.
        """
        found: Dict[str, Optional[ScheduleInfo]] = {}
        errored: set[str] = set()
        for handle in engine_handles:
            try:
                found[handle] = self.describe(handle)
            except ScheduleNotFoundError:
                found[handle] = None
            except ScheduleDescribeError:
                errored.add(handle)
        return BatchDescribeResult(found=found, errored=frozenset(errored))
