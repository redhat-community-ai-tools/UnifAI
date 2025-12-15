from typing import Any, List, Optional, Set

from config.constants import DataSource


class DocMatchScopeBuilder:
    """
    Fluent builder to resolve doc_ids and/or tags filters into 
    a set of source_ids for Qdrant vector search.
    
    Uses OR logic: returns docs matching doc_ids OR docs matching tags.
    
    Usage:
        scope = (DocMatchScopeBuilder(mongo_storage)
            .filter_by_docs(["doc_1", "doc_2"])
            .filter_by_tags(["finance"])
            .resolve())
        
        # scope is Set[str] of source_ids, or None if no filters applied
    """
    
    def __init__(self, storage: Any):
        self._storage = storage
        self._doc_ids: Optional[List[str]] = None
        self._tags: Optional[List[str]] = None
    
    def filter_by_docs(self, doc_ids: Optional[List[str]]) -> "DocMatchScopeBuilder":
        """Filter to specific document IDs."""
        if doc_ids:
            self._doc_ids = doc_ids
        return self
    
    def filter_by_tags(self, tags: Optional[List[str]]) -> "DocMatchScopeBuilder":
        """Filter to documents containing ANY of the specified tags."""
        if tags:
            self._tags = tags
        return self
    
    def resolve(self) -> Optional[Set[str]]:
        """
        Resolve filters to source_ids from MongoDB using OR logic.
        
        Returns:
            - None: No filters applied (search all documents)
            - Empty set: Filters applied but no matches found
            - Set[str]: Matching source_ids (union of doc_ids OR tags matches)
        """
        if not self._doc_ids and not self._tags:
            return None
        
        conditions = []
        
        if self._doc_ids:
            conditions.append({"source_id": {"$in": self._doc_ids}})
        
        if self._tags:
            conditions.append({"tags": {"$in": self._tags}})
        
        query = {
            "source_type": DataSource.DOCUMENT.upper_name,
            "$or": conditions
        }
        
        try:
            sources = self._storage.get_source_by_query(query)
            if not isinstance(sources, list):
                return set()
            return {s["source_id"] for s in sources if s.get("source_id")}
        except Exception:
            return set()

