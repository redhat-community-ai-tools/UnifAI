from .vector_storage import VectorStorage
from .qdrant_storage import QdrantStorage
from typing import Dict, Any
from config.app_config import AppConfig

app_config = AppConfig.get_instance()

class VectorStorageFactory:
    """Factory for creating vector storage instances based on configuration."""
    
    @staticmethod
    def create(config: Dict[str, Any]) -> VectorStorage:
        """
        Create a vector storage instance.
        
        Args:
            config: Configuration for the vector storage
            
        Returns:
            Initialized vector storage
        """
        storage_type = config.get("type", "qdrant")


        if storage_type == "qdrant":
            return QdrantStorage(
                collection_name=config.get("collection_name", "slack_data"),
                embedding_dim=config.get("embedding_dim"),
                url=app_config.qdrant_ip or config.get("url"),
                port=app_config.qdrant_port or config.get("port"),
                grpc_port=config.get("grpc_port"),
                api_key=config.get("api_key"),
                on_disk=config.get("on_disk", True),
                replication_factor=config.get("replication_factor", 1),
                write_consistency_factor=config.get("write_consistency_factor", 1)
            )
        else:
            raise ValueError(f"Unknown vector storage type: {storage_type}")