"""
Workflow schedule repository port (ABC).

Defines the persistence contract for the WorkflowSchedule aggregate.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List

from mas.core.identity import Identity
from mas.scheduling.models import RunOutcome, WorkflowSchedule


class WorkflowScheduleRepository(ABC):

    @abstractmethod
    def save(self, schedule: WorkflowSchedule) -> str:
        """Persist a new schedule. Returns the schedule id."""
        ...

    @abstractmethod
    def load(self, schedule_id: str) -> WorkflowSchedule:
        """Load a schedule by id. Raises KeyError if not found."""
        ...

    @abstractmethod
    def update(self, schedule: WorkflowSchedule) -> bool:
        """Update an existing schedule. Returns True if modified."""
        ...

    @abstractmethod
    def delete(self, schedule_id: str) -> bool:
        """Hard-delete a schedule. Returns True if deleted."""
        ...

    @abstractmethod
    def list_by_identity(
        self, identity: Identity, *, skip: int = 0, limit: int = 100,
    ) -> List[WorkflowSchedule]:
        """List schedules owned by the given identity."""
        ...

    @abstractmethod
    def find_by_blueprint(self, blueprint_id: str) -> List[WorkflowSchedule]:
        """Find all schedules for a specific blueprint."""
        ...

    @abstractmethod
    def count_active_by_blueprint(self, blueprint_id: str) -> int:
        """Count schedules with status ACTIVE or PAUSED for a blueprint."""
        ...

    @abstractmethod
    def record_run(
        self,
        schedule_id: str,
        session_id: str,
        status: RunOutcome,
        started_at: datetime,
    ) -> None:
        """Atomically increment run count and push to recent_statuses ring buffer."""
        ...
