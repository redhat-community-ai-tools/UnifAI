"""Vector storage statistics service."""
from dataclasses import dataclass
from typing import Callable, Dict, Any, Optional

from core.vector.domain.repository import VectorRepository


@dataclass
class VectorStats:
    """Vector storage statistics."""
    slack: int
    document: int
    total: int
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "slack": self.slack,
            "document": self.document,
            "total": self.total,
        }


class VectorStatsService:
    """
    Application service for vector storage statistics.
    
    Query use case that aggregates chunk counts from different vector collections.
    Uses an injected repository factory to avoid tight coupling to specific collections.
    
    Usage:
        service = VectorStatsService(vector_repo_factory=vector_repository)
        stats = service.get_chunk_counts()
        print(f"Total chunks: {stats.total}")
    """
    
    def __init__(self, vector_repo_factory: Callable[[str], VectorRepository]):
        """
        Initialize with a repository factory.
        
        Args:
            vector_repo_factory: Factory function that creates VectorRepository
                                 for a given collection name
        """
        self._repo_factory = vector_repo_factory
    
    def get_chunk_counts(self) -> VectorStats:
        """
        Get exact chunk counts for all source types.
        
        Returns:
            VectorStats with slack, document, and total counts
        """
        slack_repo = self._repo_factory("slack_data")
        doc_repo = self._repo_factory("document_data")
        
        slack = slack_repo.count(exact=True)
        document = doc_repo.count(exact=True)
        
        return VectorStats(
            slack=slack,
            document=document,
            total=slack + document,
        )
    
    def get_count_for_collection(self, collection_name: str, exact: bool = True) -> int:
        """
        Get chunk count for a specific collection.
        
        Args:
            collection_name: Name of the vector collection
            exact: Whether to perform exact count (slower but accurate)
            
        Returns:
            Number of chunks in the collection
        """
        repo = self._repo_factory(collection_name)
        return repo.count(exact=exact)

    def count_by_filter(
        self,
        collection_name: str,
        filters: Dict[str, Any],
        exact: bool = True,
    ) -> int:
        """
        Count chunks matching specific filters in a collection.
        
        This method allows counting chunks based on metadata filters,
        such as counting all chunks for a specific channel or document.
        
        Args:
            collection_name: Name of the vector collection (e.g., 'slack_data')
            filters: Dictionary of filter criteria to match
                     Example: {"metadata.channel_name": "general"}
            exact: Whether to perform exact count (slower but accurate)
            
        Returns:
            Number of chunks matching the filter criteria
            
        Example:
            # Count chunks for a specific Slack channel
            count = service.count_by_filter(
                collection_name="slack_data",
                filters={"metadata.channel_name": "engineering"},
            )
            
            # Count chunks for a specific document
            count = service.count_by_filter(
                collection_name="document_data", 
                filters={"metadata.source_id": "doc_123"},
            )
        """
        repo = self._repo_factory(collection_name)
        return repo.count(filters=filters, exact=exact)
