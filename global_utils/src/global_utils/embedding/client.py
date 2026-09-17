"""
Embedding HTTP Client - Pure transport layer.

This client handles only HTTP communication with the embedding service.
Supports OpenAI-compatible embedding endpoints (like Text Embeddings Inference).
"""

import logging
from typing import Dict, Any, List

import httpx

from global_utils.embedding.exceptions import (
    EmbeddingConnectionError,
    EmbeddingTimeoutError,
)
from global_utils.flask.correlation import correlation_headers

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """
    Pure HTTP client for embedding service.
    
    Handles only transport concerns:
    - HTTP requests/responses
    - Connection management
    - Timeout handling
    
    Example:
        client = EmbeddingClient(
            base_url="http://embedding-service:5002",
            timeout=60,
        )
        raw_response = client.post_embeddings(["text1", "text2"], model="all-MiniLM-L6-v2")
    """
    
    def __init__(
        self, 
        base_url: str,
        timeout: int = 60,
        truncate: bool = True,
    ):
        """
        Initialize the HTTP client.
        
        Args:
            base_url: Base URL for the embedding service
            timeout: Request timeout in seconds
            truncate: Whether to truncate inputs exceeding model's max tokens
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.truncate = truncate
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
        )
        logger.info(f"EmbeddingClient initialized: {self.base_url}, timeout={self.timeout}s")
    
    def post_embeddings(
        self, 
        texts: List[str], 
        model: str,
    ) -> Dict[str, Any]:
        """
        POST texts to the embedding service for embedding generation.
        
        Args:
            texts: List of text strings to embed
            model: Model name to use for embedding
        
        Returns:
            Raw JSON response from the service (OpenAI-compatible format)
            
        Raises:
            EmbeddingConnectionError: If service is unreachable
            EmbeddingTimeoutError: If request times out
        """
        url = "/v1/embeddings"
        
        try:
            payload = {
                "input": texts,
                "model": model,
                "truncate": self.truncate,
            }
            
            response = self._client.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "accept": "application/json",
                    **correlation_headers(),
                },
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.ConnectError as e:
            raise EmbeddingConnectionError(f"Cannot connect to embedding service: {e}")
        except httpx.TimeoutException as e:
            raise EmbeddingTimeoutError(f"Request timed out: {e}")
        except httpx.HTTPStatusError as e:
            raise EmbeddingConnectionError(f"HTTP error {e.response.status_code}: {e}")
        except httpx.TransportError as e:
            raise EmbeddingConnectionError(f"Transport error communicating with embedding service: {e}")

    def health_check(self) -> bool:
        """
        Check if the embedding service is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = self._client.get(
                "/health",
                timeout=10,
                headers=correlation_headers(),
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
