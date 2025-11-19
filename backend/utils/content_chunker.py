from abc import ABC, abstractmethod 
from typing import Dict, List, Any

class ContentChunker(ABC):
    """
    Abstract base class for content chunking strategies.
    
    This class defines the common interface and shared functionality
    for implementing different chunking approaches for various data sources.
    """
    
    def __init__(self, max_tokens_per_chunk: int = 500, overlap_tokens: int = 50):
        """
        Initialize the content chunker with configuration parameters.
        
        Args:
            max_tokens_per_chunk: Maximum number of tokens allowed in a single chunk
            overlap_tokens: Number of tokens to overlap between adjacent chunks
        """
        self.max_tokens_per_chunk = max_tokens_per_chunk
        self.overlap_tokens = overlap_tokens
        self._chunks = []
        
    @property
    def chunks(self) -> List[Dict[str, Any]]:
        """Return the generated chunks."""
        return self._chunks
    
    @property
    def chunk_count(self) -> int:
        """Return the number of chunks generated."""
        return len(self._chunks)
    
    @abstractmethod
    def chunk_content(self, content: Any) -> List[Dict[str, Any]]:
        """
        Split content into logical chunks according to the implemented strategy.
        
        Args:
            content: Content to be chunked (format depends on the specific source)
            
        Returns:
            List of chunks with content and metadata
        """
        pass
    
    @abstractmethod
    def estimate_token_count(self, text: str) -> int:
        """
        Estimate the number of tokens in a text string.
        
        Args:
            text: Text to analyze
            
        Returns:
            Estimated token count
        """
        pass