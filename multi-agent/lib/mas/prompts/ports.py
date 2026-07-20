"""
Schedule port (ABC) -- outbound port for schedule orchestration.

Abstracts Temporal's Schedules API behind a domain port so the
domain never imports temporalio.
"""
from abc import ABC, abstractmethod

from mas.prompts.models import ScheduledPrompt


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
