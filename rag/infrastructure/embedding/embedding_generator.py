"""
Default EmbeddingGenerator implementation.

Wraps an EmbeddingPort to add batch processing and logging.
The concrete adapter (local SentenceTransformer or remote HTTP service) is
injected at construction time; this class is adapter-agnostic.
"""

import time
import logging
from typing import Dict, List, Any, Iterator

import numpy as np

from core.vector.domain.embedder import EmbeddingGenerationError, EmbeddingGenerator, EmbeddingPort

logger = logging.getLogger(__name__)


class DefaultEmbeddingGenerator(EmbeddingGenerator):
    """
    Concrete implementation of EmbeddingGenerator.

    Implements batch processing and logging using an EmbeddingPort for the
    actual encoding. Any encoding failure propagates immediately so callers
    are aware of the problem rather than silently receiving corrupted data.
    """
    
    def __init__(self, port: EmbeddingPort, batch_size: int = 32):
        self._port = port
        self._batch_size = batch_size
        logger.info(
            f"DefaultEmbeddingGenerator initialized: "
            f"dim={self.embedding_dim}, batch_size={batch_size}"
        )
    
    @property
    def is_remote(self) -> bool:
        return self._port.is_remote

    @property
    def embedding_dim(self) -> int:
        return self._port.embedding_dim
    
    def generate_embeddings(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not chunks:
            logger.warning("No chunks provided for embedding generation")
            return []
        
        start_time = time.time()
        logger.info(f"Starting embedding generation for {len(chunks)} chunks")
        
        result_chunks = []
        
        for batch in self._batch_generator(chunks):
            texts = [chunk["text"] for chunk in batch]
            # TODO: consider adding retry logic here for transient remote failures
            embeddings = self._port.encode_texts(texts)
            for vector in embeddings:
                self._check_dimension(vector)

            for i, chunk in enumerate(batch):
                enriched_chunk = chunk.copy()
                enriched_chunk["embedding"] = embeddings[i]
                result_chunks.append(enriched_chunk)
        
        elapsed_time = time.time() - start_time
        logger.info(f"Embedding generation completed in {elapsed_time:.2f} seconds")
        
        return result_chunks
    
    def generate_query_embedding(self, query: str) -> np.ndarray:
        if not query:
            raise ValueError("Query text is empty")
        vector = self._port.encode_single(query)
        self._check_dimension(vector)
        return vector

    def _check_dimension(self, vector: Any) -> None:
        """Fail at the source when the model and the configured dimension disagree.

        A mismatch otherwise surfaces later as an opaque vector-store error, or not at
        all for a collection created with the wrong size.
        """
        size = len(vector)
        if size != self.embedding_dim:
            raise EmbeddingGenerationError(
                f"The embedding model returned {size}-dimension vectors but EMBEDDING_DIM is "
                f"{self.embedding_dim}: set EMBEDDING_DIM to the model's output size"
            )
    
    def test_connection(self) -> bool:
        return self._port.test_connection()
    
    def _batch_generator(self, chunks: List[Dict[str, Any]]) -> Iterator[List[Dict[str, Any]]]:
        for i in range(0, len(chunks), self._batch_size):
            yield chunks[i:i + self._batch_size]
