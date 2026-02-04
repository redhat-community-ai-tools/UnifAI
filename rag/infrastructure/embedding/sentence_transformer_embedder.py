import time
from typing import Dict, List, Any, Optional
from core.vector.domain.embedder import EmbeddingGenerator
from shared.logger import logger
import numpy as np
from sentence_transformers import SentenceTransformer

class SentenceTransformerEmbedding(EmbeddingGenerator):
    """
    Singleton embedding generator using the SentenceTransformers library.
    
    Implements efficient, high-quality embeddings for text chunks
    using state-of-the-art transformer models.
    """

    _instance = None

    def __new__(cls, model_name: str = "all-MiniLM-L6-v2", batch_size: int = 32, device: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super(SentenceTransformerEmbedding, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self, 
        model_name: str = "all-MiniLM-L6-v2", 
        batch_size: int = 32,
        device: Optional[str] = None
    ):
        """
        Initialize the SentenceTransformer embedding generator.
        
        Args:
            model_name: Name of the pre-trained sentence transformer model
            batch_size: Number of chunks to process in a single batch
            device: Device to run the model on (e.g., "cpu", "cuda"). None for auto.
        """
        if self._initialized:
            return

        self.model_name = model_name
        self.device = device
        
        # Initialize the model
        logger.info(f"Loading SentenceTransformer model: {model_name}")
        self.model = SentenceTransformer(model_name, device=device)
        
        # Set embedding dimension based on the loaded model
        embedding_dim = self.model.get_sentence_embedding_dimension()
        super().__init__(batch_size, embedding_dim)

        logger.info(f"Initialized embedding generator with dimension: {embedding_dim}")
        self._initialized = True

    def generate_embeddings(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for all chunks using SentenceTransformer.
        
        Args:
            chunks: List of chunks with text and metadata
            
        Returns:
            List of chunks with embeddings added
        """
        if not chunks:
            logger.warning("No chunks provided for embedding generation")
            return []
        
        start_time = time.time()
        logger.info(f"Starting embedding generation for {len(chunks)} chunks")
        
        result_chunks = []
        batch_index = 0
        
        for batch in self._batch_generator(chunks):
            batch_index += 1
            logger.debug(f"Processing batch {batch_index} with {len(batch)} chunks")
            
            # Extract text from chunks
            texts = [chunk["text"] for chunk in batch]
            
            # Generate embeddings for the batch
            embeddings = self.model.encode(texts, show_progress_bar=False)
            
            # Add embeddings to chunks
            for i, chunk in enumerate(batch):
                enriched_chunk = chunk.copy()
                enriched_chunk["embedding"] = embeddings[i]
                result_chunks.append(enriched_chunk)
        
        elapsed_time = time.time() - start_time
        logger.info(f"Embedding generation completed in {elapsed_time:.2f} seconds")
        
        return result_chunks
    
    def generate_query_embedding(self, query: str) -> np.ndarray:
        """
        Generate an embedding for a search query.
        
        Args:
            query: Search query text
            
        Returns:
            Embedding vector for the query
        """
        if not query:
            raise ValueError("Query text is empty")
        
        embedding = self.model.encode(query)
        return embedding

