"""
Workflow scheduling domain models.

Defines the WorkflowSchedule aggregate, ScheduleDefinition value object,
and supporting enums for the workflow scheduling domain.
"""
import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mas.core.identity import Identity

_MIN_INTERVAL = timedelta(minutes=1)

_CRON_FIELD_RE = re.compile(r"^[A-Za-z0-9*/,-]+$")

_VALID_TIMEZONES = frozenset(available_timezones())

_USER_PROMPT_KEY = "user_prompt"


def _is_valid_cron(expression: str) -> bool:
    fields = expression.split()
    if len(fields) != 5:
        return False
    return all(_CRON_FIELD_RE.match(field) for field in fields)


class PromptSource(str, Enum):
    MANUAL = "manual"
    SHORTCUT_COPY = "shortcut_copy"


class ScheduleStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class ScheduleOverlapPolicy(str, Enum):
    SKIP = "skip"
    BUFFER_ONE = "buffer_one"
    CANCEL_OTHER = "cancel_other"


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
        if self.interval is not None and self.interval < _MIN_INTERVAL:
            raise ValueError(f"interval must be at least {_MIN_INTERVAL}")
        if self.cron_expression is not None and not _is_valid_cron(self.cron_expression):
            raise ValueError(
                "cron_expression must be a 5-field cron string (minute hour day month weekday)"
            )
        if self.timezone not in _VALID_TIMEZONES:
            raise ValueError(f"Unknown timezone: {self.timezone}")
        if self.remaining_actions is not None and self.remaining_actions < 0:
            raise ValueError("remaining_actions must be non-negative")
        if self.start_at and self.end_at and self.start_at >= self.end_at:
            raise ValueError("start_at must be before end_at")
        return self


class RunOutcome(str, Enum):
    """Fixed outcome set for scheduled workflow runs."""
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunStatusEntry(BaseModel):
    """Single entry in the recent-runs ring buffer."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    status: RunOutcome
    started_at: Optional[datetime] = None


class RunStats(BaseModel):
    """Lightweight run-history summary embedded in the schedule aggregate."""

    total_runs: int = 0
    last_run_at: Optional[datetime] = None
    recent_statuses: List[RunStatusEntry] = Field(default_factory=list)


class WorkflowSchedule(BaseModel):
    """Workflow schedule — identity-owned configuration that causes a
    blueprint to execute on a recurring schedule.

    Each tick produces a session.  The schedule is the configuration;
    ``inputs.user_prompt`` is the content; sessions are the output.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    blueprint_id: str
    identity: Identity
    inputs: Dict[str, Any] = Field(default_factory=dict)
    source: PromptSource = PromptSource.MANUAL
    schedule: ScheduleDefinition
    schedule_status: ScheduleStatus = ScheduleStatus.ACTIVE
    engine_handle: Optional[str] = None
    completed_at: Optional[datetime] = None
    run_stats: RunStats = Field(default_factory=RunStats)
    credential_user_id: str = ""

    @property
    def user_prompt(self) -> str:
        """Convenience accessor for the prompt text in inputs."""
        return str(self.inputs.get(_USER_PROMPT_KEY, ""))

    @model_validator(mode="after")
    def _require_user_prompt(self) -> "WorkflowSchedule":
        raw = self.inputs.get(_USER_PROMPT_KEY)
        if not isinstance(raw, str):
            raise ValueError("inputs.user_prompt is required")
        stripped = raw.strip()
        if not stripped:
            raise ValueError("inputs.user_prompt must not be empty")
        if stripped != raw:
            self.inputs[_USER_PROMPT_KEY] = stripped
        return self
