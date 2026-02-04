"""Retrieval application service - vector search orchestration."""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Union

from core.vector.domain.repository import VectorRepository
from core.vector.domain.embedder import EmbeddingGenerator
from core.vector.domain.model import SearchResult
from infrastructure.retrieval.source_filter_resolver import SourceFilterResolver
from shared.logger import logger


@dataclass
class SearchQuery:
    """Value object for search parameters."""
    query_text: str
    source_type: str
    top_k: int = 5
    scope: str = "public"  # "public" or "private"
    user: str = "default"
    doc_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class RetrievalService:
    """
    Application service for vector search/retrieval operations.
    
    Orchestrates:
    - Filter resolution (doc_ids, tags -> source_ids)
    - Query embedding generation
    - Vector search execution
    
    Usage:
        service = retrieval_service("DOCUMENT")  # from app_container
        results = service.search(
            query="How to reset password?",
            limit=5,
            doc_ids=["doc_1"],
        )
    """
    
    def __init__(
        self,
        embedder: EmbeddingGenerator,
        vector_repo: VectorRepository,
        filter_resolver: SourceFilterResolver,
        source_type: str = "DOCUMENT",
    ):
        self._embedder = embedder
        self._vector_repo = vector_repo
        self._filter_resolver = filter_resolver
        self._source_type = source_type
    
    def search(
        self,
        query: str,
        limit: int = 5,
        scope: str = "public",
        user: str = "default",
        doc_ids: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a vector search with optional filtering.
        
        Args:
            query: Search query text
            limit: Number of results to return
            scope: "public" or "private" - filters by upload_by if private
            user: User identifier for private scope filtering
            doc_ids: Optional list of document IDs to filter by
            tags: Optional list of tags to filter by
            
        Returns:
            List of search result dictionaries ordered by relevance
        """
        # 1. Resolve source filters (doc_ids/tags -> source_ids)
        allowed_source_ids = self._filter_resolver.resolve(
            source_type=self._source_type,
            doc_ids=doc_ids,
            tags=tags,
        )
        
        # Early exit if filters applied but no matches
        if allowed_source_ids is not None and not allowed_source_ids:
            logger.info("Filter resolved to empty set - returning no results")
            return []
        
        # 2. Build vector search filters
        filters: Dict[str, Any] = {}
        
        if allowed_source_ids:
            filters["metadata.source_id"] = list(allowed_source_ids)
        
        if scope == "private":
            filters["metadata.upload_by"] = user
        
        # 3. Generate query embedding
        query_embedding = self._embedder.generate_query_embedding(query)
        
        # 4. Execute vector search
        results = self._vector_repo.search(
            query_embedding=query_embedding.tolist(),
            top_k=limit,
            filters=filters if filters else None,
        )
        
        logger.info(f"Search returned {len(results)} results for query: {query[:50]}...")
        
        # Convert SearchResult objects to dicts for API response
        return [
            {
                "id": r.id,
                "score": r.score,
                "content": r.content,
                "metadata": r.metadata,
            }
            for r in results
        ]

    def search_with_query(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """
        Execute a vector search using a SearchQuery object.
        
        Args:
            query: SearchQuery containing search parameters
            
        Returns:
            List of search result dictionaries ordered by relevance
        """
        return self.search(
            query=query.query_text,
            limit=query.top_k,
            scope=query.scope,
            user=query.user,
            doc_ids=query.doc_ids,
            tags=query.tags,
        )
