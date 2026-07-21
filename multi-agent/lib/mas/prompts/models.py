"""
Scheduled prompt domain models.

Defines the ScheduledPrompt aggregate, ScheduleDefinition value object,
and supporting enums for the prompt scheduling domain.
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mas.core.identity import Identity
from mas.core.prompt import BasePrompt


class PromptSource(str, Enum):
    MANUAL = "manual"
    SHORTCUT_COPY = "shortcut_copy"


class ScheduleStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    DELETED = "deleted"


class ScheduleOverlapPolicy(str, Enum):
    SKIP = "skip"
    BUFFER_ONE = "buffer_one"
    CANCEL_OTHER = "cancel_other"
    ALLOW_ALL = "allow_all"


class ScheduleDefinition(BaseModel):
    """Value object -- the scheduling configuration."""

    model_config = ConfigDict(frozen=True)

    interval: Optional[timedelta] = None
    cron_expression: Optional[str] = None
    overlap_policy: ScheduleOverlapPolicy = ScheduleOverlapPolicy.SKIP
    timezone: str = "UTC"
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    remaining_actions: Optional[int] = None
    enabled: bool = True

    @model_validator(mode="after")
    def _exactly_one_trigger(self) -> "ScheduleDefinition":
        if not self.interval and not self.cron_expression:
            raise ValueError("Either interval or cron_expression is required")
        if self.interval and self.cron_expression:
            raise ValueError("Specify interval or cron_expression, not both")
        return self


class RunStatusEntry(BaseModel):
    """Single entry in the recent-runs ring buffer."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    status: str
    started_at: Optional[datetime] = None


class RunStats(BaseModel):
    """Lightweight run-history summary embedded in the prompt aggregate."""

    total_runs: int = 0
    last_run_at: Optional[datetime] = None
    recent_statuses: List[RunStatusEntry] = Field(default_factory=list)


class ScheduledPrompt(BasePrompt):
    """Standalone scheduled prompt -- identity-owned, tied to a blueprint."""

    blueprint_id: str
    identity: Identity
    inputs: Dict[str, Any] = Field(default_factory=dict)
    source: PromptSource = PromptSource.MANUAL
    schedule: ScheduleDefinition
    schedule_status: ScheduleStatus = ScheduleStatus.ACTIVE
    temporal_schedule_id: Optional[str] = None
    completed_at: Optional[datetime] = None
    run_stats: RunStats = Field(default_factory=RunStats)
