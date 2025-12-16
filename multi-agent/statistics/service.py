from typing import Dict, List, Set, TypedDict
from blueprints.service import BlueprintService
from session.service import SessionService
from resources.service import ResourcesService
from core.dto import GroupedCount
from .models import StatisticsResponse, ResourceCategoryStats


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

    def get_all(self, user_id: str) -> StatisticsResponse:
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
        blueprint_ids = self._get_user_blueprint_ids(user_id)
        total_workflows = len(blueprint_ids)
        
        # Get session statistics
        session_stats = self._get_session_stats(user_id, blueprint_ids)
        
        # Get resource statistics
        resource_stats = self._get_resource_stats(user_id)

        return StatisticsResponse(
            totalWorkflows=total_workflows,
            activeSessions=session_stats["active_count"],
            totalResources=resource_stats["total"],
            categoriesInUse=resource_stats["categories_count"],
            blueprintSessionCounts=session_stats["by_blueprint"],
            resourcesByCategory=resource_stats["by_category"]
        )

    def _get_user_blueprint_ids(self, user_id: str) -> Set[str]:
        """
        Get all blueprint IDs belonging to a user.
        
        Args:
            user_id: The user ID to get blueprints for
            
        Returns:
            Set of blueprint IDs owned by the user
        """
        return set(self._blueprint_service.list_ids(user_id=user_id))

    def _get_session_stats(self, user_id: str, valid_blueprint_ids: Set[str]) -> SessionStats:
        """
        Get session statistics for a user.
        
        Args:
            user_id: The user ID to get session stats for
            valid_blueprint_ids: Set of blueprint IDs that the user owns
            
        Returns:
            SessionStats with active_count and by_blueprint counts
        """
        # Get blueprints that have sessions for this user
        blueprints_with_sessions = set(self._session_service.get_user_blueprints(user_id))
        
        # Active = blueprints the user owns AND has sessions for
        active_blueprint_ids = valid_blueprint_ids & blueprints_with_sessions
        active_count = len(active_blueprint_ids)
        
        # Get session counts using group_count() - returns GroupedCount DTOs
        session_counts = self._session_service.group_count(
            user_id, 
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

    def _get_resource_stats(self, user_id: str) -> ResourceStats:
        """
        Get resource statistics for a user.
        
        Args:
            user_id: The user ID to get resource stats for
            
        Returns:
            ResourceStats with total, categories_count, and by_category
        """
        # Get resource aggregation using group_count() - returns GroupedCount DTOs
        resources_grouped = self._resources_service.group_count(
            user_id, 
            group_by=["category", "type"]
        )
        
        # Transform to ResourceCategoryStats format
        by_category = self._transform_resource_counts(resources_grouped)
        
        # Get total resources count
        total = self._resources_service.count(user_id)
        
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
