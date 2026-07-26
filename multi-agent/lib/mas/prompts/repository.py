"""
Scheduled prompt repository port (ABC).

Defines the persistence contract for the ScheduledPrompt aggregate.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List

from mas.core.identity import Identity
from mas.prompts.models import RunOutcome, ScheduledPrompt


class ScheduledPromptRepository(ABC):

    @abstractmethod
    def save(self, prompt: ScheduledPrompt) -> str:
        """Persist a new prompt. Returns the prompt id."""
        ...

    @abstractmethod
    def load(self, prompt_id: str) -> ScheduledPrompt:
        """Load a prompt by id. Raises KeyError if not found."""
        ...

    @abstractmethod
    def update(self, prompt: ScheduledPrompt) -> bool:
        """Update an existing prompt. Returns True if modified."""
        ...

    @abstractmethod
    def delete(self, prompt_id: str) -> bool:
        """Hard-delete a prompt. Returns True if deleted."""
        ...

    @abstractmethod
    def list_by_identity(
        self, identity: Identity, *, skip: int = 0, limit: int = 100,
    ) -> List[ScheduledPrompt]:
        """List prompts owned by the given identity."""
        ...

    @abstractmethod
    def find_by_blueprint(self, blueprint_id: str) -> List[ScheduledPrompt]:
        """Find all prompts for a specific blueprint."""
        ...

    @abstractmethod
    def count_active_by_blueprint(self, blueprint_id: str) -> int:
        """Count prompts with status ACTIVE or PAUSED for a blueprint."""
        ...

    @abstractmethod
    def record_run(
        self,
        prompt_id: str,
        session_id: str,
        status: RunOutcome,
        started_at: datetime,
    ) -> None:
        """Atomically increment run count and push to recent_statuses ring buffer."""
        ...
