from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from mas.core.dto import GroupedCount
from mas.blueprints.models.blueprint import BlueprintExecutionStats
from mas.session.domain.status import SessionStatus


class TimeSeriesPoint(BaseModel):
    """
    Single data point in a time series.

    The period granularity (hourly, daily, monthly) is determined
    by the repository implementation based on the requested time range.
    The period is truncated to the start of the bucket
    (e.g., start of the hour, day, or month).
    """
    period: datetime = Field(
        ...,
        description="Start of the time bucket (truncated to hour, day, or month depending on granularity)"
    )
    count: int = Field(
        ...,
        description="Number of items in this period"
    )


class SystemAnalyticsData(BaseModel):
    """
    Aggregated system analytics data returned by the repository layer.

    Groups session data by user+status and user+blueprint for building
    admin dashboard views (active users, top blueprints, etc.).

    The user_blueprint_counts field serves double duty:
    - User perspective: which blueprints did each user run?
    - Blueprint perspective: which users ran each blueprint?
    Both views are derived from the same (user_id, blueprint_id) grouping.

    The blueprint_stats field provides pre-aggregated execution metrics
    per blueprint (duration, success rate, last run, users list).

    Implementations should optimize for efficiency (e.g., batching
    multiple aggregations into a single database operation).
    """
    user_status_counts: List[GroupedCount] = Field(
        default_factory=list,
        description="Sessions grouped by user_id and status"
    )
    user_blueprint_counts: List[GroupedCount] = Field(
        default_factory=list,
        description="Sessions grouped by user_id and blueprint_id (used for both user and blueprint views)"
    )
    blueprint_stats: List[BlueprintExecutionStats] = Field(
        default_factory=list,
        description="Per-blueprint aggregated execution metrics"
    )


@dataclass(frozen=True)
class RuntimeElement:
    """Complete runtime element: instance + spec + resource_spec."""
    instance: Any
    spec: Any
    resource_spec: Any  # ResourceSpec with user-defined name, config, rid, type
    
    @property
    def config(self) -> Any:
        """Get config from resource_spec."""
        return self.resource_spec.config if self.resource_spec else None


class SessionMeta(BaseModel):
    """Session metadata — canonical container for all session-level context.

    The model intentionally accepts unknown fields (``extra="allow"``) so that
    callers can attach arbitrary key-value pairs without a schema change.  This
    makes ``POST /session.meta`` a single, forward-compatible write endpoint:
    the GUI can push its full notion of session state in one call and new fields
    are persisted automatically.

    Live/ephemeral fields (``typing_users``, ``participants``) are stored here
    when sent by the caller, but the ``session.meta`` endpoint additionally
    syncs them to the collaboration store (Redis) so real-time features work.
    """
    model_config = ConfigDict(extra="allow")

    title: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    source: Optional[str] = None
    schedule_id: Optional[str] = None
    prompt_text: Optional[str] = None
    status_message: Optional[str] = None
    hitl_enabled: bool = False
    # Live/presence fields — forwarded to the collaboration store when present.
    participants: Optional[List[str]] = None  # user ids currently in the session
    typing_users: Optional[List[str]] = None  # user ids currently typing


class SessionChat(BaseModel):
    """Lightweight projection of a session's chat-relevant graph state."""
    messages: List = Field(default_factory=list)
    output: str = ""
    status: Optional[str] = None
    status_message: Optional[str] = None


class SessionDetail(BaseModel):
    """Combined session payload for deep-link navigation.

    Constructed by ``SessionService.get_session_detail()`` and served
    from ``GET /sessions/session.get``.  Serialized with ``by_alias=True``
    for the frontend.
    """
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId")
    blueprint_id: str = Field(..., alias="blueprintId")
    blueprint_name: str = Field(..., alias="blueprintName")
    status: str
    meta: SessionMeta
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    completed_at: Optional[datetime] = Field(None, alias="completedAt")
    chat: SessionChat


class ScheduleRunSummary(BaseModel):
    """One execution record in a scheduled prompt's run history.

    Lives in the session domain (rather than ``mas.prompts``) because each
    run is a session — projected from session documents by
    ``SessionService.get_runs_by_schedule()``.
    """
    session_id: str
    status: SessionStatus = SessionStatus.PENDING
    started_at: Optional[str] = None  # ISO-8601
    metadata: SessionMeta = Field(default_factory=SessionMeta)