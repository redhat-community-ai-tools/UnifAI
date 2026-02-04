"""Source filter resolver - resolves doc_ids/tags to source_ids for search filtering."""
from typing import List, Optional, Set, Dict, Any

from pymongo.collection import Collection

from shared.logger import logger


class SourceFilterResolver:
    """
    Infrastructure component that resolves filters to source_ids for vector search.
    
    Directly accesses MongoDB - this is a query-only component for search filtering,
    not managing aggregate state. Keeping this separate from the repository keeps
    the repository focused on CRUD operations.
    
    Uses OR logic: returns sources matching doc_ids OR sources matching tags.
    
    Usage:
        resolver = SourceFilterResolver(sources_collection)
        source_ids = resolver.resolve(
            source_type="DOCUMENT",
            doc_ids=["doc_1", "doc_2"],
            tags=["finance"]
        )
        
        # Returns:
        # - None: No filters applied (search all)
        # - Empty set: Filters applied but no matches
        # - Set[str]: Matching source_ids
    """
    
    def __init__(self, sources_collection: Collection):
        """
        Initialize the filter resolver.
        
        Args:
            sources_collection: MongoDB collection containing source documents
        """
        self._col = sources_collection
    
    def resolve(
        self,
        source_type: str,
        doc_ids: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Set[str]]:
        """
        Resolve filters to source_ids using OR logic.
        
        Args:
            source_type: Filter by source type (e.g., "DOCUMENT", "SLACK")
            doc_ids: Optional list of specific document IDs to include
            tags: Optional list of tags - include docs with ANY of these tags
        
        Returns:
            - None: No filters applied (search all documents)
            - Empty set: Filters applied but no matches found
            - Set[str]: Matching source_ids (union of doc_ids OR tags matches)
        """
        if not doc_ids and not tags:
            return None
        
        conditions: List[Dict[str, Any]] = []
        if doc_ids:
            conditions.append({"source_id": {"$in": doc_ids}})
        if tags:
            conditions.append({"tags": {"$in": tags}})
        
        query: Dict[str, Any] = {
            "source_type": source_type.upper(),
            "$or": conditions,
        }
        
        try:
            # Only fetch source_id field for efficiency
            docs = self._col.find(query, {"source_id": 1})
            return {d["source_id"] for d in docs if d.get("source_id")}
        except Exception as e:
            logger.error(f"Error resolving source filters: {e}")
            return set()
