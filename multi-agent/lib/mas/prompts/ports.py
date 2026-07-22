"""
Schedule port (ABC) -- outbound port for schedule orchestration.

Abstracts Temporal's Schedules API behind a domain port so the
domain never imports temporalio.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from mas.prompts.models import ScheduledPrompt


class ScheduleNotFoundError(Exception):
    """Raised when a schedule does not exist in the external orchestrator."""

    def __init__(self, schedule_id: str) -> None:
        self.schedule_id = schedule_id
        super().__init__(f"Schedule not found: {schedule_id}")


@dataclass(frozen=True)
class ScheduleInfo:
    """Read-back snapshot of a schedule's live state in the orchestrator."""

    paused: bool
    remaining_actions: Optional[int]
    running: bool


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
