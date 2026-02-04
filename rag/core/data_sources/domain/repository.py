"""DataSource repository port (interface)."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from core.data_sources.domain.model import DataSource
from core.data_sources.domain.view import DataSourceView
from core.pagination.domain.model import PaginatedResult


class DataSourceRepository(ABC):
    """Port for DataSource persistence - one interface per aggregate."""

    @abstractmethod
    def find_by_id(self, source_id: str) -> Optional[DataSource]:
        """Get source by source_id."""
        ...

    @abstractmethod
    def find_by_pipeline_id(self, pipeline_id: str) -> Optional[DataSource]:
        """Get source by pipeline_id."""
        ...

    @abstractmethod
    def find_all(
        self,
        source_type: Optional[str] = None,
        view: DataSourceView = DataSourceView.SUMMARY,
    ) -> List[DataSource]:
        """Get all sources, optionally filtered by type.
        
        Args:
            source_type: Filter by source type (e.g., "DOCUMENT", "SLACK")
            view: SUMMARY for list views (excludes heavy fields like full_text),
                  FULL for complete data including all content fields
        """
        ...

    @abstractmethod
    def find_paginated(
        self,
        cursor: Optional[str] = None,
        limit: int = 50,
        source_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> PaginatedResult[Dict[str, Any]]:
        """
        Paginated query for sources.
        
        Args:
            cursor: Pagination cursor
            limit: Max items to return
            source_type: Filter by type (e.g., "DOCUMENT", "SLACK")
            search: Filter by name prefix (case-insensitive)
            
        Returns:
            PaginatedResult containing source documents
        """
        ...

    @abstractmethod
    def get_distinct_values(
        self,
        field: str,
        source_type: Optional[str] = None,
        search: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 50,
    ) -> PaginatedResult[str]:
        """
        Get distinct values from a field (e.g., tags, categories).
        
        Args:
            field: Field path to extract distinct values from (e.g., "tags")
            source_type: Filter by source type
            search: Filter values by prefix (case-insensitive)
            cursor: Pagination cursor
            limit: Max values to return
            
        Returns:
            PaginatedResult containing unique string values
        """
        ...

    @abstractmethod
    def save(self, source: DataSource) -> None:
        """Insert or update a source (upsert by pipeline_id)."""
        ...

    @abstractmethod
    def delete(self, source_id: str) -> bool:
        """Delete source by ID. Returns True if deleted."""
        ...
