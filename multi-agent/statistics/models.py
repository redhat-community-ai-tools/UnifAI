from typing import Dict, List
from pydantic import BaseModel, Field


class ResourceCategoryStats(BaseModel):
    """Statistics for resources grouped by category."""
    category: str = Field(..., description="Resource category")
    count: int = Field(..., description="Total count of resources in this category")
    types: Dict[str, int] = Field(default_factory=dict, description="Count of resources by type within this category")


class StatisticsResponse(BaseModel):
    """Response model for aggregated statistics."""
    totalWorkflows: int = Field(..., description="Total number of workflows/blueprints")
    activeSessions: int = Field(..., description="Number of active sessions")
    totalResources: int = Field(..., description="Total number of resources")
    categoriesInUse: int = Field(..., description="Number of categories with at least one configured resource")
    blueprintSessionCounts: Dict[str, int] = Field(default_factory=dict, description="Dictionary mapping blueprint_id to session count")
    resourcesByCategory: List[ResourceCategoryStats] = Field(default_factory=list, description="List of resource statistics grouped by category")

