import numpy as np
from abc import ABC, abstractmethod 
from typing import Dict, List, Any, Optional

class VectorStorage(ABC):
    """
    Abstract base class for vector storage systems.
    
    This class defines the common interface and shared functionality
    for storing and retrieving vector embeddings.
    """
    
    def __init__(self, collection_name: str):
        """
        Initialize the vector storage.
        
        Args:
            collection_name: Name of the collection to store vectors
        """
        self.collection_name = collection_name
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the storage system and create necessary structures if needed."""
        pass
    
    @abstractmethod
    def store_embeddings(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Store embeddings and their metadata in the vector storage.
        
        Args:
            chunks: List of chunks with embeddings and metadata
        """
        pass
    
    @abstractmethod
    def search(
        self, 
        query_embedding: np.ndarray, 
        top_k: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in the storage.
        
        Args:
            query_embedding: Query vector to search for
            top_k: Number of results to return
            filters: Optional filters to apply to the search
            
        Returns:
            List of search results with similarity scores and payload
        """
        pass
    
    @abstractmethod
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count vectors in the storage, optionally filtered.
        
        Args:
            filters: Optional filters to apply to the count
            
        Returns:
            Count of vectors matching the criteria
        """
        pass
    
    @abstractmethod
    def delete(self, ids: Optional[List[str]] = None, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Delete vectors from the storage.
        
        Args:
            ids: Optional list of vector IDs to delete
            filters: Optional filters to select vectors to delete
            
        Returns:
            Number of vectors deleted
        """
        pass