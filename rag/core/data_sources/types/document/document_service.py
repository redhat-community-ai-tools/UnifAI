"""Document-specific application service."""
from typing import Dict, List, Optional, Any

from core.data_sources.service import DataSourceService
from core.data_sources.domain.model import DataSource
from core.data_sources.domain.repository import DataSourceRepository
from core.pagination.domain.model import PaginatedResult


class DocumentService:
    """
    Application service for document-specific operations.
    
    Handles queries and business logic specific to DOCUMENT sources,
    such as retrieving tags and documents from successfully processed items.
    
    Uses DataSourceService for shared functionality like pipeline stats enrichment.
    """

    def __init__(
        self,
        data_source_service: DataSourceService,
        source_repo: DataSourceRepository,
    ):
        self._data_source_service = data_source_service
        self._source_repo = source_repo

    def list_available_docs(
        self,
        cursor: Optional[str] = None,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> PaginatedResult[Dict[str, Any]]:
        """
        Get paginated list of DONE documents for dropdown selection.
        
        Filters to only successfully processed (DONE) documents and
        normalizes the response format for UI consumption.
        
        Args:
            cursor: Pagination cursor
            limit: Max items to return
            search: Filter by name prefix
            
        Returns:
            PaginatedResult with normalized docs {id, name, upload_by}
        """
        # Get paginated sources
        result = self._source_repo.find_paginated(
            cursor=cursor,
            limit=limit,
            source_type="DOCUMENT",
            search=search,
        )
        
        # Convert to domain models for enrichment
        sources = [DataSource.from_dict(d) for d in result.data]
        enriched = self._data_source_service.enrich_with_pipeline_stats(sources)
        
        # Filter to DONE only and normalize
        done_docs = [
            {"id": s["source_id"], "name": s["source_name"], "upload_by": s["upload_by"]}
            for s in enriched
            if s.get("status") == "DONE"
        ]
        
        return PaginatedResult(
            data=done_docs,
            next_cursor=result.next_cursor,
            has_more=result.has_more,
            total=len(done_docs),  # Approximate due to post-filtering
        )

    def get_available_tags(
        self,
        cursor: Optional[str] = None,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> PaginatedResult[Dict[str, str]]:
        """
        Get tags from DONE documents only (for UI dropdowns).
        
        Unlike the shared get_distinct_tags(), this filters to only include
        tags from successfully processed documents.
        
        Args:
            cursor: Pagination cursor
            limit: Max tags to return
            search: Filter tags by prefix (case-insensitive)
            
        Returns:
            PaginatedResult with tag options [{label, value}]
        """
        # Get all DONE sources
        all_sources = self._source_repo.find_all(source_type="DOCUMENT")
        enriched = self._data_source_service.enrich_with_pipeline_stats(all_sources)
        done_sources = [s for s in enriched if s.get("status") == "DONE"]
        
        # Extract unique tags from DONE sources
        all_tags: set = set()
        for s in done_sources:
            all_tags.update(s.get("tags", []))
        
        # Apply search filter (case-insensitive prefix match)
        if search:
            search_lower = search.lower()
            all_tags = {t for t in all_tags if t.lower().startswith(search_lower)}
        
        # Sort alphabetically and paginate
        sorted_tags = sorted(all_tags)
        skip = int(cursor) if cursor and cursor.isdigit() else 0
        page = sorted_tags[skip:skip + limit]
        
        next_cursor = str(skip + len(page)) if skip + len(page) < len(sorted_tags) else None
        
        return PaginatedResult(
            data=[{"label": t, "value": t} for t in page],
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
            total=len(sorted_tags),
        )
