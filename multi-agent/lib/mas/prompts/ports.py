"""
Schedule port (ABC) -- outbound port for schedule orchestration.

Abstracts Temporal's Schedules API behind a domain port so the
domain never imports temporalio.
"""
from abc import ABC, abstractmethod
from typing import Dict, FrozenSet, List, Optional

from pydantic import BaseModel, Field

from mas.prompts.models import ScheduledPrompt


class ScheduleNotFoundError(Exception):
    """Raised when a schedule does not exist in the external orchestrator."""

    def __init__(self, schedule_id: str) -> None:
        self.schedule_id = schedule_id
        super().__init__(f"Schedule not found: {schedule_id}")


class ScheduleDescribeError(Exception):
    """Transient failure while describing a schedule (e.g. RPC timeout)."""

    def __init__(self, schedule_id: str) -> None:
        self.schedule_id = schedule_id
        super().__init__(f"Transient describe failure: {schedule_id}")


class ScheduleValidationError(ValueError):
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

    ``found`` maps schedule IDs to their info (None = confirmed not found).
    ``errored`` contains IDs whose lookup failed due to transient errors.
    """

    model_config = {"frozen": True}

    found: Dict[str, Optional[ScheduleInfo]] = Field(default_factory=dict)
    errored: FrozenSet[str] = frozenset()


class SchedulePort(ABC):

    @abstractmethod
    def create_schedule(self, prompt: ScheduledPrompt) -> str:
        """Create a Temporal schedule for the prompt. Returns the schedule ID."""
        ...

    @abstractmethod
    def pause(self, temporal_schedule_id: str) -> None:
        """Pause a running schedule."""
        ...

    @abstractmethod
    def resume(self, temporal_schedule_id: str) -> None:
        """Resume a paused schedule."""
        ...

    @abstractmethod
    def delete(self, temporal_schedule_id: str) -> None:
        """Delete a schedule permanently."""
        ...

    @abstractmethod
    def update_schedule(self, temporal_schedule_id: str, prompt: ScheduledPrompt) -> None:
        """Atomically update an existing schedule in-place."""
        ...

    @abstractmethod
    def trigger_now(self, temporal_schedule_id: str) -> None:
        """Trigger an immediate execution of the schedule (one-off)."""
        ...

    @abstractmethod
    def describe(self, temporal_schedule_id: str) -> ScheduleInfo:
        """Read-back the schedule's live state from the orchestrator."""
        ...

    def describe_batch(self, schedule_ids: List[str]) -> BatchDescribeResult:
        """Batch read-back of multiple schedules' live state.

        Default implementation falls back to sequential describe() calls.
        """
        found: Dict[str, Optional[ScheduleInfo]] = {}
        errored: set[str] = set()
        for sid in schedule_ids:
            try:
                found[sid] = self.describe(sid)
            except ScheduleNotFoundError:
                found[sid] = None
            except ScheduleDescribeError:
                errored.add(sid)
        return BatchDescribeResult(found=found, errored=frozenset(errored))
