import logging
from typing import Dict, List, Set, TypedDict, Optional
from datetime import datetime, timezone
from mas.blueprints.service import BlueprintService
from mas.session.service import SessionService
from mas.resources.service import ResourcesService
from mas.core.identity import Identity
from mas.core.dto import GroupedCount
from mas.blueprints.models.blueprint import BlueprintExecutionStats
from global_utils.utils.time_utils import format_utc_iso
from .models import (
    StatisticsResponse, ResourceCategoryStats, SystemStatsResponse,
    TotalStats, UserActivity, BlueprintUsage
)

logger = logging.getLogger(__name__)


class SessionStats(TypedDict):
    """Internal structure for session statistics."""
    active_count: int
    by_blueprint: Dict[str, int]


class ResourceStats(TypedDict):
    """Internal structure for resource statistics."""
    total: int
    categories_count: int
    by_category: List[ResourceCategoryStats]


class StatisticsService:
    """
    Service for aggregating statistics for all features.
    Centralizes the logic for collecting and formatting workflow, session, and resource statistics.
    
    Architecture:
        - get_all() orchestrates the collection of statistics
        - _get_user_blueprint_ids() handles blueprint domain
        - _get_session_stats() handles session domain with helper _transform_session_counts()
        - _get_resource_stats() handles resource domain with helper _transform_resource_counts()
    """

    def __init__(
        self,
        blueprint_service: BlueprintService,
        session_service: SessionService,
        resources_service: ResourcesService
    ):
        """
        Initialize the StatisticsService.

        Args:
            blueprint_service: Service for blueprint operations
            session_service: Service for session operations
            resources_service: Service for resource operations
        """
        self._blueprint_service = blueprint_service
        self._session_service = session_service
        self._resources_service = resources_service

    def get_all(self, identity: Identity) -> StatisticsResponse:
        """
        Get aggregated statistics for all features.
        Returns all stats in a single response for optimal performance.

        This method orchestrates the collection of statistics from different domains,
        delegating to focused helper methods for each area.

        Args:
            user_id: The user ID to get statistics for

        Returns:
            StatisticsResponse: Pydantic model containing all statistics
        """
        # Get blueprint IDs (workflow domain)
        blueprint_ids = self._get_user_blueprint_ids(identity)
        total_workflows = len(blueprint_ids)
        
        # Get session statistics
        session_stats = self._get_session_stats(identity, blueprint_ids)
        # Get resource statistics
        resource_stats = self._get_resource_stats(identity)

        return StatisticsResponse(
            totalWorkflows=total_workflows,
            activeSessions=session_stats["active_count"],
            totalResources=resource_stats["total"],
            categoriesInUse=resource_stats["categories_count"],
            blueprintSessionCounts=session_stats["by_blueprint"],
            resourcesByCategory=resource_stats["by_category"]
        )

    def _get_user_blueprint_ids(self, identity: Identity) -> Set[str]:
        """
        Get all blueprint IDs belonging to a user.
        
        Args:
            user_id: The user ID to get blueprints for
            
        Returns:
            Set of blueprint IDs owned by the user
        """
        return set(self._blueprint_service.list_ids(identity=identity))

    def _get_session_stats(self, identity: Identity, valid_blueprint_ids: Set[str]) -> SessionStats:
        """
        Get session statistics for an identity (user or team).
        """
        # Get blueprints that have sessions for this user
        blueprints_with_sessions = set(self._session_service.get_user_blueprints(identity))
        
        # Active = blueprints the user owns AND has sessions for
        active_blueprint_ids = valid_blueprint_ids & blueprints_with_sessions
        active_count = len(active_blueprint_ids)
        
        # Get session counts using group_count() - returns GroupedCount DTOs
        session_counts = self._session_service.group_count(
            identity,
            group_by=["blueprint_id"]
        )
        
        # Transform to dict, filtered to user's own blueprints
        by_blueprint = self._transform_session_counts(session_counts, valid_blueprint_ids)
        
        return SessionStats(
            active_count=active_count,
            by_blueprint=by_blueprint
        )

    def _transform_session_counts(
        self, 
        grouped_counts: List[GroupedCount], 
        valid_blueprint_ids: Set[str]
    ) -> Dict[str, int]:
        """
        Transform session GroupedCount results to blueprint->count dict.
        
        Filters results to only include blueprints the user owns.
        
        Args:
            grouped_counts: List of GroupedCount DTOs from session service
            valid_blueprint_ids: Set of blueprint IDs to filter by
            
        Returns:
            Dict mapping blueprint_id to session count
        """
        return {
            item.get("blueprint_id"): item.count
            for item in grouped_counts
            if item.get("blueprint_id") in valid_blueprint_ids
        }

    def _get_resource_stats(self, identity: Identity) -> ResourceStats:
        """
        Get resource statistics for a user.
        
        Args:
            user_id: The user ID to get resource stats for
            
        Returns:
            ResourceStats with total, categories_count, and by_category
        """
        # Get resource aggregation using group_count() - returns GroupedCount DTOs
        resources_grouped = self._resources_service.group_count(
            identity,
            group_by=["category", "type"]
        )
        
        # Transform to ResourceCategoryStats format
        by_category = self._transform_resource_counts(resources_grouped)
        # Get total resources count
        total = self._resources_service.count(identity)
        
        return ResourceStats(
            total=total,
            categories_count=len(by_category),
            by_category=by_category
        )

    def _transform_resource_counts(
        self, 
        grouped_counts: List[GroupedCount]
    ) -> List[ResourceCategoryStats]:
        """
        Transform resource GroupedCount results to ResourceCategoryStats list.
        
        Groups by category and collects types within each category.
        
        Args:
            grouped_counts: List of GroupedCount DTOs from resource service
            
        Returns:
            List of ResourceCategoryStats with category totals and type breakdowns
        """
        # Group by category and collect types within each category
        category_data: Dict[str, Dict] = {}
        
        for item in grouped_counts:
            category = item.get("category")
            type_name = item.get("type")
            count = item.count
            
            if not category:
                continue
                
            if category not in category_data:
                category_data[category] = {"count": 0, "types": {}}
            
            category_data[category]["count"] += count
            if type_name:
                category_data[category]["types"][type_name] = count
        
        return [
            ResourceCategoryStats(category=cat, count=data["count"], types=data["types"])
            for cat, data in category_data.items()
        ]

    # ---------- System-wide Stats (for admin dashboard) ----------

    def get_system_stats(self, since: Optional[datetime] = None) -> SystemStatsResponse:
        """
        Get system-wide statistics for admin dashboard.
        
        All data is scoped to the given time range. The client can call this
        method with different `since` values to get different views
        (e.g., today, last 7 days, last 30 days, all time).
        
        Args:
            since: Optional cutoff datetime for filtering. None means all time.
        
        Returns:
            SystemStatsResponse containing all system-wide statistics data
        """
        # Get system analytics data (batched aggregation via single $facet call).
        # Derive total_runs, unique_users, and status_breakdown from the
        # user_status_counts grouping to avoid 3 extra DB round-trips.
        analytics = self._session_service.get_system_analytics(since=since)
        
        total_runs, unique_users, status_breakdown = self._derive_totals_from_status_counts(
            analytics.user_status_counts
        )
        blueprints_used = len(analytics.blueprint_stats)
        
        total_stats = TotalStats(
            total_runs=total_runs,
            unique_users=unique_users,
            blueprints_used=blueprints_used
        )
        
        # Build active users list from analytics data
        active_users = self._build_user_activity_list(
            analytics.user_status_counts,
            analytics.user_blueprint_counts
        )
        
        # Build top blueprints list from analytics data
        top_blueprints = self._build_blueprint_usage_list(
            analytics.blueprint_stats,
            limit=10
        )
        
        # Get session activity time series
        time_series = self._session_service.get_session_activity_series(since=since)
        
        return SystemStatsResponse(
            total_stats=total_stats,
            status_breakdown=status_breakdown,
            active_users=active_users,
            top_blueprints=top_blueprints,
            time_series=time_series,
            generated_at=format_utc_iso(datetime.now(timezone.utc))
        )

    def _build_user_activity_list(
        self,
        status_counts: List[GroupedCount],
        blueprint_counts: List[GroupedCount],
        limit: int = 500
    ) -> List[UserActivity]:
        """
        Build a list of UserActivity models from grouped count data.
        
        Combines user+status counts with user+blueprint counts into
        structured UserActivity models.
        
        Args:
            status_counts: Sessions grouped by user_id and status
            blueprint_counts: Sessions grouped by user_id and blueprint_id
            limit: Optional limit on number of results
        
        Returns:
            List of UserActivity models sorted by run count descending
        """
        # Aggregate run counts and status breakdown by user
        user_data: Dict[str, UserActivity] = {}
        for item in status_counts:
            user_id = item.get("user_id")
            status = item.get("status")
            count = item.count
            
            if not user_id:
                continue

            if user_id not in user_data:
                user_data[user_id] = UserActivity(user_id=user_id)
            
            user_data[user_id].run_count += count
            if status:
                current = user_data[user_id].status_breakdown.get(status, 0)
                user_data[user_id].status_breakdown[status] = current + count
        
        # Count unique blueprints per user
        user_blueprints: Dict[str, Set[str]] = {}
        for item in blueprint_counts:
            user_id = item.get("user_id")
            blueprint_id = item.get("blueprint_id")
            if user_id:
                if user_id not in user_blueprints:
                    user_blueprints[user_id] = set()
                if blueprint_id:
                    user_blueprints[user_id].add(blueprint_id)
        
        for user_id, activity in user_data.items():
            activity.blueprints_used = len(user_blueprints.get(user_id, set()))
        
        # Sort by run count descending
        result = sorted(user_data.values(), key=lambda x: x.run_count, reverse=True)
        
        if limit:
            result = result[:limit]
        
        return result

    @staticmethod
    def _derive_totals_from_status_counts(
        status_counts: List[GroupedCount],
    ) -> tuple:
        """
        Derive total_runs, unique_users, and status_breakdown from
        user+status grouped counts, avoiding separate DB round-trips.
        
        Args:
            status_counts: Sessions grouped by user_id and status
            
        Returns:
            Tuple of (total_runs, unique_users, status_breakdown dict)
        """
        total_runs = 0
        user_ids: Set[str] = set()
        status_breakdown: Dict[str, int] = {}
        
        for item in status_counts:
            count = item.count
            total_runs += count
            
            user_id = item.get("user_id")
            if user_id:
                user_ids.add(user_id)
            
            status = item.get("status")
            if status:
                status_breakdown[status] = status_breakdown.get(status, 0) + count
        
        return total_runs, len(user_ids), status_breakdown

    def _build_blueprint_usage_list(
        self,
        blueprint_stats: List[BlueprintExecutionStats],
        limit: int = 10
    ) -> List[BlueprintUsage]:
        """
        Transform BlueprintExecutionStats into BlueprintUsage models.
        
        Adds blueprint name lookup and calculates derived metrics (success rate %).
        
        Args:
            blueprint_stats: Pre-aggregated execution metrics from repository
            limit: Maximum number of blueprints to return
        
        Returns:
            List of BlueprintUsage models sorted by run count descending
        """
        # Sort by total_runs to get top blueprints first
        sorted_stats = sorted(blueprint_stats, key=lambda s: s.total_runs, reverse=True)[:limit]
        
        # Batch lookup blueprint names (only for top N)
        blueprint_ids = [s.blueprint_id for s in sorted_stats]
        blueprint_names = self._batch_get_blueprint_names(blueprint_ids)
        
        # Transform to BlueprintUsage models
        result = []
        for stats in sorted_stats:
            terminal_runs = stats.completed_runs + stats.failed_runs
            success_rate = round((stats.completed_runs / terminal_runs) * 100, 1) if terminal_runs > 0 else 0.0
            avg_duration_seconds = max(0.0, stats.avg_duration_ms / 1000.0) if stats.avg_duration_ms is not None else None
            
            result.append(BlueprintUsage(
                blueprint_id=stats.blueprint_id,
                blueprint_name=blueprint_names[stats.blueprint_id],
                run_count=stats.total_runs,
                unique_users=len(stats.users),
                avg_duration_seconds=avg_duration_seconds,
                last_run_at=stats.last_run,
                success_rate=success_rate,
                completed_runs=stats.completed_runs,
                failed_runs=stats.failed_runs,
                in_progress_runs=stats.total_runs - terminal_runs,
                user_list=stats.users
            ))
        
        return result

    def _batch_get_blueprint_names(self, blueprint_ids: List[str]) -> Dict[str, str]:
        """
        Get blueprint names for multiple blueprints in a single DB query.
        
        Args:
            blueprint_ids: List of blueprint IDs to look up
        
        Returns:
            Dictionary mapping blueprint_id to blueprint_name.
            Falls back to blueprint_id as the name for missing or invalid entries.
        """
        if not blueprint_ids:
            return {}
        
        try:
            docs = self._blueprint_service.load_many(blueprint_ids)
        except Exception as e:
            logger.warning("Failed to batch-load blueprint names for %s: %s", blueprint_ids, e)
            return {bp_id: bp_id for bp_id in blueprint_ids}
        
        names = {}
        for doc in docs:
            spec_dict = doc.spec_dict
            if isinstance(spec_dict, dict):
                names[doc.blueprint_id] = spec_dict.get("name", doc.blueprint_id)
            else:
                names[doc.blueprint_id] = doc.blueprint_id
        
        for bp_id in blueprint_ids:
            if bp_id not in names:
                names[bp_id] = bp_id
        
        return names
