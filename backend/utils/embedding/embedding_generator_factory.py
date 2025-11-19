import torch
from typing import Dict, Any
from .sentence_transformer_embedding import SentenceTransformerEmbedding
from .embedding_generator import EmbeddingGenerator

device = "cuda" if torch.cuda.is_available() else "cpu"

# Factory class for creating embedding generators
class EmbeddingGeneratorFactory:
    """Factory for creating embedding generator instances based on configuration."""
    
    @staticmethod
    def create(config: Dict[str, Any]) -> EmbeddingGenerator:
        """
        Create an embedding generator instance.
        
        Args:
            config: Configuration for the embedding generator
            
        Returns:
            Initialized embedding generator
        """
        generator_type = config.get("type", "sentence_transformer")
        
        if generator_type == "sentence_transformer":
            return SentenceTransformerEmbedding(
                model_name=config.get("model_name", "all-MiniLM-L6-v2"),
                batch_size=config.get("batch_size", 32),
                device=config.get("device", device)
            )
        else:
            raise ValueError(f"Unknown embedding generator type: {generator_type}")