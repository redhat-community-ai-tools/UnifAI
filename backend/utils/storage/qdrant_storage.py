import os
import time
import uuid
import numpy as np
import qdrant_client
from typing import Dict, List, Any, Optional
from qdrant_client.http import models as qmodels
from .vector_storage import VectorStorage
from shared.logger import logger

class QdrantStorage(VectorStorage):
    """
    Vector storage implementation using Qdrant.
    
    Qdrant is a vector similarity search engine with extended filtering
    capabilities, ideal for efficient retrieval in RAG systems.
    """
    
    def __init__(
        self,
        collection_name: str,
        embedding_dim: int,
        url: Optional[str] = None,
        port: Optional[int] = None,
        grpc_port: Optional[int] = None,
        api_key: Optional[str] = None,
        on_disk: bool = True,
        replication_factor: int = 1,
        write_consistency_factor: int = 1
    ):
        """
        Initialize the Qdrant storage.
        
        Args:
            collection_name: Name of the collection in Qdrant
            embedding_dim: Dimension of the embedding vectors
            url: URL of the Qdrant server (e.g., "http://localhost")
            port: HTTP port of the Qdrant server (default: 6333)
            grpc_port: gRPC port of the Qdrant server (default: 6334)
            api_key: API key for Qdrant Cloud (if applicable)
            on_disk: Whether to store vectors on disk (True) or in memory (False)
            replication_factor: Number of replicas for each segment
            write_consistency_factor: How many replicas should confirm write
        """
        super().__init__(collection_name)
        self.embedding_dim = embedding_dim
        self.on_disk = on_disk
        self.replication_factor = replication_factor
        self.write_consistency_factor = write_consistency_factor
        
        # Use environment variables as fallback
        self.url = url or os.getenv("QDRANT_URL", "http://localhost")
        self.port = port or int(os.getenv("QDRANT_PORT", "6333"))
        self.grpc_port = grpc_port or int(os.getenv("QDRANT_GRPC_PORT", "6334"))
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        
        # Initialize client
        if self.url.startswith(("http://", "https://")):
            # HTTP client
            self.client = qdrant_client.QdrantClient(
                url=self.url,
                port=self.port,
                api_key=self.api_key,
                prefer_grpc=False
            )
        else:
            # gRPC client
            self.client = qdrant_client.QdrantClient(
                host=self.url,
                port=self.grpc_port,
                api_key=self.api_key,
                prefer_grpc=True
            )
        
        logger.info(f"Initialized Qdrant client connecting to {self.url}")
    
    def initialize(self) -> None:
        """
        Initialize the Qdrant collection with the appropriate schema.
        
        Creates the collection if it doesn't exist and sets up necessary
        vector configuration and payload schema.
        """
        # Check if collection exists
        collections = self.client.get_collections().collections
        collection_names = [collection.name for collection in collections]
        
        if self.collection_name in collection_names:
            logger.info(f"Collection '{self.collection_name}' already exists")
            return
        
        # Create collection with vector configuration
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(
                size=self.embedding_dim,
                distance=qmodels.Distance.COSINE
            ),
            optimizers_config=qmodels.OptimizersConfigDiff(
                indexing_threshold=10000,  # Build index after 10k vectors
            ),
            replication_factor=self.replication_factor,
            write_consistency_factor=self.write_consistency_factor,
            on_disk_payload=self.on_disk
        )
        
        # Create payload indexes for common metadata fields to speed up filtering
        self._create_payload_index("metadata.source_type", qmodels.PayloadSchemaType.KEYWORD)
        self._create_payload_index("metadata.channel_name", qmodels.PayloadSchemaType.KEYWORD)
        self._create_payload_index("metadata.source_id", qmodels.PayloadSchemaType.KEYWORD)
        
        logger.info(f"Created collection '{self.collection_name}' with dimension {self.embedding_dim}")
    
    def _create_payload_index(self, field_name: str, field_type: qmodels.PayloadSchemaType) -> None:
        """
        Create an index on a payload field for faster filtering.
        
        Args:
            field_name: Name of the field to index
            field_type: Type of the field for indexing
        """
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field_name,
                field_schema=field_type
            )
            logger.debug(f"Created payload index on '{field_name}'")
        except Exception as e:
            logger.warning(f"Failed to create payload index on '{field_name}': {e}")
    
    def store_embeddings(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Store chunk embeddings in Qdrant.
        
        Args:
            chunks: List of chunks with embeddings and metadata
        """
        if not chunks:
            logger.warning("No chunks provided for storage")
            return
        
        start_time = time.time()
        logger.info(f"Storing {len(chunks)} embeddings in Qdrant collection '{self.collection_name}'")
        
        # Prepare points for batch upload
        points = []
        
        for chunk in chunks:
            # Ensure chunk has required fields
            if "embedding" not in chunk:
                logger.warning(f"Chunk missing embedding, skipping")
                continue
                
            # Generate a unique ID for the chunk
            chunk_id = str(uuid.uuid4())
            
            # Prepare the point for Qdrant
            point = qmodels.PointStruct(
                id=chunk_id,
                vector=chunk["embedding"].tolist(),
                payload={
                    "text": chunk["text"],
                    "metadata": chunk["metadata"]
                }
            )
            
            points.append(point)
        
        # Upload points in batches
        batch_size = 100  # Qdrant recommended batch size
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch
            )
            logger.debug(f"Uploaded batch of {len(batch)} points to Qdrant")
        
        elapsed_time = time.time() - start_time
        logger.info(f"Stored {len(points)} embeddings in {elapsed_time:.2f} seconds")
    
    def search(
        self, 
        query_embedding: np.ndarray, 
        top_k: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in Qdrant.
        
        Args:
            query_embedding: Query vector to search for
            top_k: Number of results to return
            filters: Optional filters to apply to the search
            
        Returns:
            List of search results with similarity scores and payload
        """
        # Convert filters to Qdrant filter format if provided
        qdrant_filter = None
        if filters:
            qdrant_filter = self._convert_filters_to_qdrant(filters)
        
        # Perform the search
        search_results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding.tolist(),
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True
        )
        
        # Convert to standard format
        results = []
        for result in search_results.points:
            results.append({
                "id": result.id,
                "score": result.score,
                "content": result.payload.get("text", ""),
                "metadata": result.payload.get("metadata", {})
            })
        
        return results
    
    def count(self, filters: Optional[Dict[str, Any]] = None, exact: bool = False) -> int:
        """
        Count vectors in the Qdrant collection, optionally filtered.
        
        Args:
            filters: Optional filters to apply to the count
            
        Returns:
            Count of vectors matching the criteria
        """
        # Convert filters to Qdrant filter format if provided
        qdrant_filter = None
        if filters:
            qdrant_filter = self._convert_filters_to_qdrant(filters)
        
        # Get count
        count_result = self.client.count(
            collection_name=self.collection_name,
            count_filter=qdrant_filter,
            exact=exact
        )
        
        return count_result.count
    
    def delete(self, ids: Optional[List[str]] = None, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Delete vectors from Qdrant.
        
        Args:
            ids: Optional list of vector IDs to delete
            filters: Optional filters to select vectors to delete
            
        Returns:
            Number of vectors deleted
        """
        if ids is not None:
            # Delete by IDs
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qmodels.PointIdsList(
                    points=ids
                ),
                wait=True
            )
            return len(ids)
        
        elif filters is not None:
            # Get count before deletion for reporting
            count_before = self.count(filters)
            
            # Convert filters to Qdrant filter format
            qdrant_filter = self._convert_filters_to_qdrant(filters)
            
            # Delete by filter
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qmodels.FilterSelector(
                    filter=qdrant_filter
                ),
                wait=True
            )
            
            return count_before
        
        else:
            raise ValueError("Either ids or filters must be provided for deletion")
    
    def _convert_filters_to_qdrant(self, filters: Dict[str, Any]) -> qmodels.Filter:
        """
        Convert generic filters to Qdrant-specific filter format.
        
        Args:
            filters: Dictionary of filter conditions
            
        Returns:
            Qdrant filter object
        """
        must_conditions = []
        
        for field, value in filters.items():
            if isinstance(value, list):
                # Handle list of values (OR condition)
                should_conditions = [
                    qmodels.FieldCondition(
                        key=field,
                        match=qmodels.MatchValue(value=v)
                    )
                    for v in value
                ]
                must_conditions.append(qmodels.Filter(should=should_conditions))
            else:
                # Handle single value
                must_conditions.append(
                    qmodels.FieldCondition(
                        key=field,
                        match=qmodels.MatchValue(value=value)
                    )
                )
        
        return qmodels.Filter(must=must_conditions)
    
    def delete_source(self, source_id: str, source_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete all embeddings for a specific source from Qdrant.
        
        Args:
            source_id: The ID of the source to delete
            source_type: Optional source type for additional filtering
            
        Returns:
            Dictionary with deletion results
        """
        try:
            # Build filter for source deletion
            filters = {"metadata.source_id": source_id}
            if source_type:
                filters["metadata.source_type"] = source_type.upper()
            
            # Count embeddings to be deleted
            deleted_count = self.count(filters=filters)
            logger.info(f"Found {deleted_count} embeddings to delete for source {source_id}")
            
            if deleted_count == 0:
                logger.warning(f"No embeddings found in Qdrant for source {source_id}")
                return {
                    "success": True,
                    "embeddings_deleted": 0,
                    "message": f"No embeddings found for source {source_id}"
                }
            
            # Delete embeddings
            self.delete(filters=filters)
            logger.info(f"Deleted {deleted_count} embeddings from Qdrant for source {source_id}")
            
            # Verify deletion (exact count with brief polling)
            max_wait_seconds = int(os.getenv("QDRANT_DELETE_VERIFY_TIMEOUT_SECONDS", "10"))
            poll_interval_seconds = 0.5
            waited = 0.0
            remaining_count = self.count(filters=filters, exact=True)
            while remaining_count > 0 and waited < max_wait_seconds:
                time.sleep(poll_interval_seconds)
                waited += poll_interval_seconds
                remaining_count = self.count(filters=filters, exact=True)

            if remaining_count > 0:
                logger.error(f"Deletion incomplete: {remaining_count} embeddings still remain for source {source_id} after waiting {waited:.1f}s")
                return {
                    "success": False,
                    "embeddings_deleted": max(0, deleted_count - remaining_count),
                    "remaining_count": remaining_count,
                    "error": f"Deletion incomplete, {remaining_count} embeddings remain"
                }
            
            logger.info(f"Successfully verified deletion - no embeddings remain for source {source_id}")
            return {
                "success": True,
                "embeddings_deleted": deleted_count,
                "message": f"Successfully deleted all embeddings for source {source_id}"
            }
                
        except Exception as e:
            logger.error(f"Error deleting source {source_id} from Qdrant: {e}")
            return {
                "success": False,
                "embeddings_deleted": 0,
                "error": str(e)
            }