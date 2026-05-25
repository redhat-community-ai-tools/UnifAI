from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from mas.core.dto import GroupedCount
from mas.blueprints.models.blueprint import BlueprintExecutionStats


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
    status_message: Optional[str] = None
    # Live/presence fields — forwarded to the collaboration store when present.
    participants: Optional[List[str]] = None  # user ids currently in the session
    typing_users: Optional[List[str]] = None  # user ids currently typing


class SessionChat(BaseModel):
    """Lightweight projection of a session's chat-relevant graph state."""
    messages: List = Field(default_factory=list)
    output: str = ""
    status: Optional[str] = None
    status_message: Optional[str] = None
