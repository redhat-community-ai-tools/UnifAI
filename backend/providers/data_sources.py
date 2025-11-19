from dataclasses import asdict
from utils.storage.mongo.mongo_helpers import get_mongo_storage
from shared.logger import logger
from utils.embedding.embedding_generator_factory import EmbeddingGeneratorFactory
from utils.storage.vector_storage_factory import VectorStorageFactory
from utils.storage.qdrant_storage import QdrantStorage
from utils.storage.storage_deletion_manager import SourceDeletionManager
from shared.config import EmbeddingConfig, StorageConfig

def initialize_embedding_generator():
    """
    Initialize and return the embedding generator.
    
    Returns:
        EmbeddingGenerator: Configured embedding generator instance
    """
    embedding_config = asdict(EmbeddingConfig())
    return EmbeddingGeneratorFactory.create(embedding_config)

def initialize_vector_storage(embedding_dim: int = 384, source_type: str = "data_source"):
    """
    Initialize and return the vector storage.
    
    Args:
        embedding_dim: Dimension of the embeddings (default: 384)
        source_type: Type of data source for collection naming (default: "data_source")
        
    Returns:
        VectorStorage: Configured and initialized vector storage instance
    """
    storage_config = asdict(StorageConfig(collection_name=f"{source_type.lower()}_data"))
    storage_config["embedding_dim"] = embedding_dim
    vector_storage = VectorStorageFactory.create(storage_config)
    vector_storage.initialize()
    return vector_storage


def initialize_storage_manager(source_type: str = "data_source"):
    """Initialize and return storage manager for operations."""
    embedding_generator = initialize_embedding_generator()
    vector_storage = initialize_vector_storage(embedding_generator.embedding_dim, source_type)
    
    mongo_storage = get_mongo_storage()
    vector_store = vector_storage if isinstance(vector_storage, QdrantStorage) else None
    if not vector_store:
        raise RuntimeError("Expected QdrantStorage instance")
    
    return SourceDeletionManager(vector_store, mongo_storage)

def get_available_data_sources(source_type: str):
    """
    Fetches a list of available data sources of a specific type.
    
    Args:
        source_type: The type of data source (e.g., 'DOCUMENT', 'DATABASE', etc.)
        user: Optional user filter to get sources for a specific user
        
    Returns:
        List of available data sources matching the criteria
    """
    try:
        svc = get_mongo_storage()
        source_type_upper = source_type.upper()      
        all_sources = svc.list_sources(source_type_upper)       
        return all_sources
        
    except Exception as e:
        logger.error(f"Failed to get available data sources for type {source_type}: {str(e)}")
        return []   

def delete_data_source(source_id: str):
    """
    Delete a data source by its pipeline ID.
    
    Args:
        source_id: The ID of the pipeline/source to delete
        source_type: Optional source type for additional validation/logging
        
    Returns:
        dict: Result of deletion operation with success status and details
    """
    try:
        # First get the source info to determine the actual source type and source_id
        mongo_storage = get_mongo_storage()
        source_info = mongo_storage.get_source_info_by_source_id(source_id)
        actual_source_type = None
        if source_info.get("success"):
            actual_source_type = source_info.get("source_type")
        
        # Initialize storage manager with the correct source type
        storage_manager = initialize_storage_manager(actual_source_type if actual_source_type else "data_source")
        
        result = storage_manager.delete_source(source_id, actual_source_type)

        return {
            "success": result.get("success", False),
            "result": {
                "source_id": result.get("source_id"),
                "source_name": result.get("source_name"),
                # Map counts directly from deletion result
                "qdrant_embeddings_deleted": result.get("embeddings_deleted", 0),
                "mongo_source_deleted": result.get("source_deleted", False),
                "mongo_pipelines_deleted": result.get("pipelines_deleted", 0)
            }
        }
    except Exception as e:
        logger.error(f"Failed to delete channel {source_id}: {e}")
        raise e

def get_data_source_by_id(pipeline_id: str, source_type: str = None):
    """
    Get a specific data source by its pipeline ID.
    
    Args:
        pipeline_id: The ID of the pipeline/source to retrieve
        source_type: Optional source type for additional filtering
        
    Returns:
        dict: Data source information or None if not found
    """
    try:
        svc = get_mongo_storage()
        source = svc.get_source(pipeline_id)
        
        # Additional type validation if specified
        if source and source_type:
            if source.get('source_type', '').upper() != source_type.upper():
                logger.warning(f"Source type mismatch for {pipeline_id}. Expected: {source_type}, Found: {source.get('source_type')}")
                return None
                
        return source
        
    except Exception as e:
        logger.error(f"Failed to get data source {pipeline_id}: {str(e)}")
        return None
