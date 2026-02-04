"""Vector repository port (interface)."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from core.vector.domain.model import VectorChunk, SearchResult


class VectorRepository(ABC):
    """Port for vector storage operations."""

    def __init__(self, collection_name: str):
        """
        Initialize the vector storage.
        
        Args:
            collection_name: Name of the collection to store vectors
        """
        self.collection_name = collection_name
    

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the vector storage.
        
        Creates the collection/index if it doesn't exist and sets up
        necessary configuration.
        """
        ...

    @abstractmethod
    def store(self, chunks: List[VectorChunk]) -> int:
        """
        Store vector chunks in the storage.
        
        Args:
            chunks: List of VectorChunk objects to store
            
        Returns:
            Number of chunks successfully stored
        """
        ...

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Search for similar vectors.
        
        Args:
            query_embedding: Query vector to search for
            top_k: Number of results to return
            filters: Optional filters to apply to the search
            
        Returns:
            List of SearchResult objects with similarity scores
        """
        ...

    @abstractmethod
    def count(self, filters: Optional[Dict[str, Any]] = None, exact: bool = False) -> int:
        """
        Count vectors in the storage.
        
        Args:
            filters: Optional filters to apply to the count
            exact: Whether to perform exact count (slower but accurate)
            
        Returns:
            Count of vectors matching the criteria
        """
        ...

    @abstractmethod
    def delete(self, ids: Optional[List[str]] = None) -> int:
        """
        Delete vectors by their IDs.
        
        Args:
            ids: List of vector IDs to delete
            
        Returns:
            Number of vectors deleted
        """
        ...

    @abstractmethod
    def delete_by_filter(self, filters: Dict[str, Any]) -> int:
        """
        Delete vectors matching a filter.
        
        Args:
            filters: Filters to select vectors to delete
            
        Returns:
            Number of vectors deleted
        """
        ... 

    @abstractmethod
    def delete_by_source_id(self, source_id: str) -> int:
        """
        Delete vectors by source ID.
        
        Args:
            source_id: Source ID to delete vectors for
        Returns:
            Number of vectors deleted
        """
        ...