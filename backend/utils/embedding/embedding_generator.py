import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Iterator

class EmbeddingGenerator(ABC):
    """
    Abstract base class for embedding generation.
    
    This class defines the common interface and shared functionality
    for creating vector embeddings from text chunks.
    """
    
    def __init__(self, batch_size: int = 32, embedding_dim: Optional[int] = None):
        """
        Initialize the embedding generator.
        
        Args:
            batch_size: Number of chunks to process in a single batch
            embedding_dim: Dimension of the generated embeddings (model specific)
        """
        self.batch_size = batch_size
        self.embedding_dim = embedding_dim
        
    @abstractmethod
    def generate_embeddings(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for a list of text chunks.
        
        Args:
            chunks: List of chunks with text and metadata
            
        Returns:
            List of chunks with embeddings added
        """
        pass
    
    @abstractmethod
    def generate_query_embedding(self, query: str) -> np.ndarray:
        """
        Generate an embedding for a search query.
        
        Args:
            query: Search query text
            
        Returns:
            Embedding vector for the query
        """
        pass
    
    def _batch_generator(self, chunks: List[Dict[str, Any]]) -> Iterator[List[Dict[str, Any]]]:
        """
        Split chunks into batches for efficient processing.
        
        Args:
            chunks: List of chunks to batch
            
        Yields:
            Batches of chunks
        """
        for i in range(0, len(chunks), self.batch_size):
            yield chunks[i:i + self.batch_size]

    