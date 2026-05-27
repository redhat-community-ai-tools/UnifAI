from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field
from mas.session.domain.models import TimeSeriesPoint


class TimeRangePreset(str, Enum):
    """
    Predefined time range presets for statistics filtering.

    Used at the API layer to accept human-readable time range values.
    Convert to a cutoff datetime with to_since() for use in
    service and repository layers.
    """
    TODAY = "today"
    LAST_7_DAYS = "7days"
    LAST_30_DAYS = "30days"
    ALL = "all"

    def to_since(self) -> Optional[datetime]:
        """
        Convert preset to a UTC cutoff datetime.

        Returns:
            Cutoff datetime in UTC, or None for ALL (no time limit)
        """
        now = datetime.now(timezone.utc)
        if self == TimeRangePreset.TODAY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self == TimeRangePreset.LAST_7_DAYS:
            return now - timedelta(days=7)
        elif self == TimeRangePreset.LAST_30_DAYS:
            return now - timedelta(days=30)
        return None


# ---------- User-scoped Statistics Models ----------

class ResourceCategoryStats(BaseModel):
    """Statistics for resources grouped by category."""
    category: str = Field(..., description="Resource category")
    count: int = Field(..., description="Total count of resources in this category")
    types: Dict[str, int] = Field(default_factory=dict, description="Count of resources by type within this category")


class StatisticsResponse(BaseModel):
    """Response model for aggregated statistics (user-scoped)."""
    totalWorkflows: int = Field(..., description="Total number of workflows/blueprints")
    activeSessions: int = Field(..., description="Number of active sessions")
    totalResources: int = Field(..., description="Total number of resources")
    categoriesInUse: int = Field(..., description="Number of categories with at least one configured resource")
    blueprintSessionCounts: Dict[str, int] = Field(default_factory=dict, description="Dictionary mapping blueprint_id to session count")
    resourcesByCategory: List[ResourceCategoryStats] = Field(default_factory=list, description="List of resource statistics grouped by category")


# ---------- System-wide Statistics Models (for admin dashboard) ----------

class TotalStats(BaseModel):
    """Total statistics for system-wide overview."""
    total_runs: int = Field(..., description="Total number of workflow runs")
    unique_users: int = Field(..., description="Number of unique identities (users and teams)")
    blueprints_used: int = Field(..., description="Number of distinct blueprints executed")


class UserActivity(BaseModel):
    """
    Identity activity statistics for admin dashboard.

    Represents a single identity's (user or team) session activity within a
    given time range, including run counts, status breakdown, and blueprint usage.
    """
    identity_id: str = Field(..., description="Identity identifier (username or team ID)")
    identity_type: str = Field("user", description="Identity type: 'user' or 'team'")
    display_name: str = Field("", description="Human-readable display name (team name or username)")
    run_count: int = Field(0, description="Number of session runs in the time period")
    status_breakdown: Dict[str, int] = Field(default_factory=dict, description="Run counts broken down by session status")
    blueprints_used: int = Field(0, description="Number of distinct blueprints used")


class BlueprintUsage(BaseModel):
    """
    Blueprint usage statistics for admin dashboard.

    Represents how a single blueprint has been used across the system,
    including total runs, number of distinct users, and execution metrics.
    """
    blueprint_id: str = Field(..., description="Blueprint identifier")
    blueprint_name: str = Field(..., description="Blueprint display name")
    run_count: int = Field(0, description="Total number of session runs")
    unique_users: int = Field(0, description="Number of distinct users who ran this blueprint")
    avg_duration_seconds: Optional[float] = Field(
        None,
        description="Average execution duration in seconds (null if no completed runs with timing data)"
    )
    last_run_at: Optional[str] = Field(
        None,
        description="ISO timestamp of most recent execution"
    )
    success_rate: float = Field(
        0.0,
        description="Percentage of COMPLETED runs out of terminal runs (0.0 - 100.0)"
    )
    completed_runs: int = Field(0, description="Number of COMPLETED executions")
    failed_runs: int = Field(0, description="Number of FAILED executions")
    in_progress_runs: int = Field(0, description="Number of non-terminal executions (PENDING, QUEUED, RUNNING)")
    user_list: List[str] = Field(
        default_factory=list,
        description="List of identities who executed this blueprint (format: 'type:id', e.g. 'user:alice', 'team:abc123')"
    )


class SystemStatsResponse(BaseModel):
    """
    Response model for system-wide statistics (admin dashboard).

    All data is scoped to the requested time range. The client can
    call the endpoint with different time_range values to get
    different views (e.g., today, last 7 days, last 30 days).
    """
    total_stats: TotalStats = Field(..., description="Total statistics: total_runs, unique_users, blueprints_used")
    status_breakdown: Dict[str, int] = Field(default_factory=dict, description="Breakdown of session runs by status")
    active_users: List[UserActivity] = Field(default_factory=list, description="Users active in the selected time range, sorted by run count")
    top_blueprints: List[BlueprintUsage] = Field(default_factory=list, description="Most used blueprints in the selected time range")
    time_series: List[TimeSeriesPoint] = Field(default_factory=list, description="Session activity over time")
    generated_at: str = Field(..., description="ISO timestamp (UTC) when statistics were generated")
