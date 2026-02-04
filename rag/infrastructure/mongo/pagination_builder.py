"""
Fluent builder for paginated MongoDB queries.

Single source of truth for all pagination logic.
Supports documents and distinct values modes.
"""
import re
from typing import Optional, Dict, Any, List

from pymongo.collection import Collection

from core.pagination.domain.model import PaginatedResult
from shared.logger import logger


class PaginatedQueryBuilder:
    """
    Fluent builder for paginated MongoDB queries.
    
    Single source of truth for all pagination logic across repositories.
    Supports two modes:
    - documents(): Return full documents
    - distinct(field): Return unique values from a field
    
    Example:
        result = (PaginatedQueryBuilder(collection)
            .with_filter({"source_type": "DOCUMENT"})
            .with_search("test", field="source_name")
            .with_sort("created_at", desc=True)
            .paginate(cursor="10", limit=50)
            .documents())
        
        # Returns PaginatedResult with data, next_cursor, has_more, total
    """

    def __init__(self, collection: Collection):
        """
        Initialize builder with a MongoDB collection.
        
        Args:
            collection: PyMongo Collection instance
        """
        self._col = collection
        self._filters: List[Dict[str, Any]] = []
        self._sort_field = "_id"
        self._sort_order = -1
        self._cursor: Optional[str] = None
        self._limit = 50
        self._search_regex: Optional[str] = None
        self._search_field = "name"

    # ══════════════════════════════════════════════════════════════════════════
    # Fluent Configuration
    # ══════════════════════════════════════════════════════════════════════════

    def with_filter(self, filter_dict: Dict[str, Any]) -> "PaginatedQueryBuilder":
        """
        Add filter conditions (merged with existing filters).
        
        Can be called multiple times to add more conditions.
        
        Args:
            filter_dict: MongoDB query filter
            
        Returns:
            Self for chaining
        """
        if filter_dict:
            self._filters.append(filter_dict)
        return self

    def with_search(
        self, 
        pattern: Optional[str], 
        field: str = "name"
    ) -> "PaginatedQueryBuilder":
        """
        Add regex search on a specific field.
        
        Uses start-anchored, case-insensitive matching.
        
        Args:
            pattern: Search pattern (will be regex-escaped)
            field: Field to search in
            
        Returns:
            Self for chaining
        """
        self._search_regex = pattern
        self._search_field = field
        return self

    def with_sort(
        self, 
        field: str, 
        desc: bool = True
    ) -> "PaginatedQueryBuilder":
        """
        Set sort field and order.
        
        Args:
            field: Field to sort by
            desc: True for descending (newest first), False for ascending
            
        Returns:
            Self for chaining
        """
        self._sort_field = field
        self._sort_order = -1 if desc else 1
        return self

    def paginate(
        self, 
        cursor: Optional[str] = None, 
        limit: int = 50
    ) -> "PaginatedQueryBuilder":
        """
        Set pagination parameters.
        
        Args:
            cursor: Opaque cursor from previous response (skip count as string)
            limit: Maximum items to return
            
        Returns:
            Self for chaining
        """
        self._cursor = cursor
        self._limit = limit
        return self

    # ══════════════════════════════════════════════════════════════════════════
    # Execution Methods (terminal operations)
    # ══════════════════════════════════════════════════════════════════════════

    def documents(self) -> PaginatedResult[Dict[str, Any]]:
        """
        Execute query and return full documents.
        
        Returns:
            PaginatedResult containing document dicts
        """
        return self._execute(distinct_field=None)

    def distinct(self, field: str) -> PaginatedResult[str]:
        """
        Execute query and return distinct values from a field.
        
        Useful for tags, categories, or any field with repeated values.
        
        Args:
            field: Dot-notation path to field (e.g., "tags", "metadata.category")
            
        Returns:
            PaginatedResult containing unique string values
        """
        return self._execute(distinct_field=field)

    # ══════════════════════════════════════════════════════════════════════════
    # Internal Helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_cursor(self) -> int:
        """Parse cursor string to skip value."""
        if self._cursor and self._cursor.isdigit():
            return int(self._cursor)
        return 0

    def _build_search_match(self, field: str) -> Dict[str, Any]:
        """Build regex match condition for search."""
        if not self._search_regex:
            return {}
        pattern = f"^{re.escape(self._search_regex)}"
        return {field: {"$regex": pattern, "$options": "i"}}

    def _compute_pagination(
        self, 
        skip: int, 
        fetched_count: int, 
        total: int
    ) -> tuple:
        """Compute next_cursor and has_more from counts."""
        next_pos = skip + fetched_count
        if next_pos < total:
            return str(next_pos), True
        return None, False

    def _execute(self, distinct_field: Optional[str]) -> PaginatedResult:
        """
        Execute the paginated query.
        
        Args:
            distinct_field: If set, extract unique values from this field.
                           If None, return full documents.
        """
        skip = self._parse_cursor()
        pipeline = []

        # Merge all filters into single $match
        if self._filters:
            merged_filter = {}
            for f in self._filters:
                merged_filter.update(f)
            pipeline.append({"$match": merged_filter})

        if distinct_field:
            # ─── DISTINCT VALUES MODE ─────────────────────────────────────
            pipeline.append({"$unwind": f"${distinct_field}"})
            
            search_match = self._build_search_match(distinct_field)
            if search_match:
                pipeline.append({"$match": search_match})
            else:
                # Filter out null/empty values
                pipeline.append({"$match": {
                    distinct_field: {"$exists": True, "$nin": [None, ""]}
                }})
            
            pipeline.append({"$group": {"_id": f"${distinct_field}"}})
            pipeline.append({"$sort": {"_id": self._sort_order}})
        else:
            # ─── FULL DOCUMENTS MODE ──────────────────────────────────────
            search_match = self._build_search_match(self._search_field)
            if search_match:
                pipeline.append({"$match": search_match})
            pipeline.append({"$sort": {self._sort_field: self._sort_order}})

        # Facet for efficient count + data in single query
        pipeline.append({
            "$facet": {
                "metadata": [{"$count": "total"}],
                "data": [{"$skip": skip}, {"$limit": self._limit}]
            }
        })

        try:
            result = list(self._col.aggregate(pipeline))

            # Parse aggregation result
            total = 0
            items = []
            if result and result[0]:
                facet = result[0]
                if facet.get("metadata"):
                    total = facet["metadata"][0]["total"]
                
                if distinct_field:
                    items = [item["_id"] for item in facet.get("data", [])]
                else:
                    items = facet.get("data", [])

            next_cursor, has_more = self._compute_pagination(skip, len(items), total)

            return PaginatedResult(
                data=items,
                next_cursor=next_cursor,
                has_more=has_more,
                total=total
            )
        except Exception as e:
            logger.error(f"Error in paginated query: {e}")
            return PaginatedResult(data=[], next_cursor=None, has_more=False, total=0)

