"""Qdrant adapter for VectorRepository port."""
import os
import time
import uuid
from typing import Optional, List, Dict, Any

import qdrant_client
from qdrant_client.http import models as qmodels

from core.vector.domain.model import VectorChunk, SearchResult
from core.vector.domain.repository import VectorRepository
from infrastructure.qdrant.sparse_encoder import HashingBM25Encoder
import logging

logger = logging.getLogger("rag_pipeline")

# Hybrid collections carry named vectors and live beside the legacy ones, so enabling hybrid search never
# rewrites an existing collection: sources are re-ingested into the new one.
HYBRID_SUFFIX = "_hybrid"
DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"
# Stable point ids: re-running a pipeline overwrites a source's chunks instead of duplicating them.
POINT_ID_NAMESPACE = uuid.UUID("6f1c3a52-6b4e-4f43-9a55-3d6f5b0e8a1d")


class CollectionMismatchError(RuntimeError):
    """An existing collection was created with another vector size or layout."""


class QdrantVectorRepository(VectorRepository):
    """
    Qdrant implementation of VectorRepository port.
    
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
        write_consistency_factor: int = 1,
        hybrid: bool = False,
        client: Optional[qdrant_client.QdrantClient] = None,
    ):
        """
        Initialize the Qdrant vector repository.
        
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
            hybrid: Use a dense + sparse (BM25) collection, named <collection_name>_hybrid
            client: Pre-built client (tests use QdrantClient(":memory:"))
        """
        self._hybrid = hybrid
        self._collection_name = collection_name + (HYBRID_SUFFIX if hybrid else "")
        self._sparse = HashingBM25Encoder() if hybrid else None
        self._embedding_dim = embedding_dim
        self._on_disk = on_disk
        self._replication_factor = replication_factor
        self._write_consistency_factor = write_consistency_factor

        # Use environment variables as fallback
        self._url = url or os.getenv("QDRANT_URL", "http://localhost")
        self._port = port or int(os.getenv("QDRANT_PORT", "6333"))
        self._grpc_port = grpc_port or int(os.getenv("QDRANT_GRPC_PORT", "6334"))
        self._api_key = api_key or os.getenv("QDRANT_API_KEY")

        # Initialize client
        self._client = client or self._create_client()
        logger.info(f"Initialized Qdrant client connecting to {self._url}")

    def _create_client(self) -> qdrant_client.QdrantClient:
        """Create the Qdrant client based on URL format."""
        if self._url.startswith(("http://", "https://")):
            # HTTP client
            return qdrant_client.QdrantClient(
                url=self._url,
                port=self._port,
                api_key=self._api_key,
                prefer_grpc=False,
            )
        else:
            # gRPC client
            return qdrant_client.QdrantClient(
                host=self._url,
                port=self._grpc_port,
                api_key=self._api_key,
                prefer_grpc=True,
            )

    def initialize(self) -> None:
        """
        Initialize the Qdrant collection with the appropriate schema.
        
        Creates the collection if it doesn't exist and sets up necessary
        vector configuration and payload schema.
        """
        # Check if collection exists
        collections = self._client.get_collections().collections
        collection_names = [collection.name for collection in collections]

        if self._collection_name in collection_names:
            self._check_existing_collection()
            logger.info(f"Collection '{self._collection_name}' already exists")
            return

        dense = qmodels.VectorParams(size=self._embedding_dim, distance=qmodels.Distance.COSINE)
        extra: Dict[str, Any] = {}
        if self._hybrid:
            extra["sparse_vectors_config"] = {SPARSE_VECTOR: qmodels.SparseVectorParams(modifier=qmodels.Modifier.IDF)}

        # Create collection with vector configuration
        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config={DENSE_VECTOR: dense} if self._hybrid else dense,
            **extra,
            optimizers_config=qmodels.OptimizersConfigDiff(
                indexing_threshold=10000,  # Build index after 10k vectors
            ),
            replication_factor=self._replication_factor,
            write_consistency_factor=self._write_consistency_factor,
            on_disk_payload=self._on_disk,
        )

        # Create payload indexes for common metadata fields to speed up filtering
        self._create_payload_index("metadata.source_type", qmodels.PayloadSchemaType.KEYWORD)
        self._create_payload_index("metadata.channel_name", qmodels.PayloadSchemaType.KEYWORD)
        self._create_payload_index("metadata.source_id", qmodels.PayloadSchemaType.KEYWORD)
        self._create_payload_index("metadata.owner_id", qmodels.PayloadSchemaType.KEYWORD)

        logger.info(f"Created collection '{self._collection_name}' with dimension {self._embedding_dim}")

    def _check_existing_collection(self) -> None:
        """Refuse to write into a collection whose vectors do not match this repository's settings."""
        vectors = self._client.get_collection(self._collection_name).config.params.vectors
        if self._hybrid:
            params = vectors.get(DENSE_VECTOR) if isinstance(vectors, dict) else None
            if params is None:
                raise CollectionMismatchError(
                    f"Collection '{self._collection_name}' has no named '{DENSE_VECTOR}' vector: it was not created for hybrid search"
                )
        else:
            params = vectors if not isinstance(vectors, dict) else None
            if params is None:
                raise CollectionMismatchError(
                    f"Collection '{self._collection_name}' uses named vectors; enable hybrid search to use it"
                )
        if params.size != self._embedding_dim:
            raise CollectionMismatchError(
                f"Collection '{self._collection_name}' stores {params.size}-dimension vectors but the embedding model "
                f"produces {self._embedding_dim}: use another collection or re-create it"
            )

    @staticmethod
    def point_id(chunk: VectorChunk) -> str:
        """The chunk's own id, else a stable id from (source_id, chunk_index), else a random one."""
        if chunk.id:
            return chunk.id
        meta = chunk.metadata or {}
        source_id, index = meta.get("source_id"), meta.get("chunk_index")
        if source_id is not None and index is not None:
            return str(uuid.uuid5(POINT_ID_NAMESPACE, f"{source_id}:{index}"))
        return str(uuid.uuid4())

    def _create_payload_index(self, field_name: str, field_type: qmodels.PayloadSchemaType) -> None:
        """Create an index on a payload field for faster filtering."""
        try:
            self._client.create_payload_index(
                collection_name=self._collection_name,
                field_name=field_name,
                field_schema=field_type,
            )
            logger.debug(f"Created payload index on '{field_name}'")
        except Exception as e:
            logger.warning(f"Failed to create payload index on '{field_name}': {e}")

    def store(self, chunks: List[VectorChunk]) -> int:
        """
        Store vector chunks in Qdrant.
        
        Args:
            chunks: List of VectorChunk objects to store
            
        Returns:
            Number of chunks successfully stored
        """
        if not chunks:
            logger.warning("No chunks provided for storage")
            return 0

        start_time = time.time()
        logger.info(f"Storing {len(chunks)} embeddings in Qdrant collection '{self._collection_name}'")

        # Prepare points for batch upload
        points = []

        for chunk in chunks:
            if not chunk.embedding:
                logger.warning("Chunk missing embedding, skipping")
                continue

            vector: Any = chunk.embedding
            if self._hybrid:
                sparse = self._sparse.encode_document(chunk.text or "")
                vector = {DENSE_VECTOR: chunk.embedding,
                          SPARSE_VECTOR: qmodels.SparseVector(indices=sparse.indices, values=sparse.values)}

            # Prepare the point for Qdrant
            point = qmodels.PointStruct(
                id=self.point_id(chunk),
                vector=vector,
                payload={
                    "text": chunk.text,
                    "metadata": chunk.metadata,
                },
            )

            points.append(point)

        # Upload points in batches
        batch_size = 100  # Qdrant recommended batch size
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self._client.upsert(
                collection_name=self._collection_name,
                points=batch,
            )
            logger.debug(f"Uploaded batch of {len(batch)} points to Qdrant")

        elapsed_time = time.time() - start_time
        logger.info(f"Stored {len(points)} embeddings in {elapsed_time:.2f} seconds")

        return len(points)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        query_text: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Search for similar vectors in Qdrant.
        
        Args:
            query_embedding: Query vector to search for
            top_k: Number of results to return
            filters: Optional filters to apply to the search
            query_text: The query as text; in a hybrid collection it adds a sparse (BM25) candidate list
                fused with the dense one by reciprocal rank fusion. Fused scores are rank-based (about
                0.01-0.05), not cosine similarities.
            
        Returns:
            List of SearchResult objects with similarity scores
        """
        # Convert filters to Qdrant filter format if provided
        qdrant_filter = self._convert_filters(filters) if filters else None

        if self._hybrid and query_text and query_text.strip():
            sparse = self._sparse.encode_query(query_text)
            candidates = max(top_k * 4, 20)
            search_results = self._client.query_points(
                collection_name=self._collection_name,
                prefetch=[
                    qmodels.Prefetch(query=query_embedding, using=DENSE_VECTOR, limit=candidates, filter=qdrant_filter),
                    qmodels.Prefetch(query=qmodels.SparseVector(indices=sparse.indices, values=sparse.values),
                                     using=SPARSE_VECTOR, limit=candidates, filter=qdrant_filter),
                ],
                query=qmodels.FusionQuery(fusion=qmodels.Fusion.RRF),
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
            )
        else:
            # Perform the search
            search_results = self._client.query_points(
                collection_name=self._collection_name,
                query=query_embedding,
                using=DENSE_VECTOR if self._hybrid else None,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
            )

        # Convert to domain SearchResult objects
        results = []
        for result in search_results.points:
            results.append(
                SearchResult(
                    id=str(result.id),
                    score=result.score,
                    content=result.payload.get("text", ""),
                    metadata=result.payload.get("metadata", {}),
                )
            )

        return results

    def count(self, filters: Optional[Dict[str, Any]] = None, exact: bool = False) -> int:
        """
        Count vectors in the Qdrant collection.
        
        Args:
            filters: Optional filters to apply to the count
            exact: Whether to perform exact count (slower but accurate)
            
        Returns:
            Count of vectors matching the criteria
        """
        qdrant_filter = self._convert_filters(filters) if filters else None

        count_result = self._client.count(
            collection_name=self._collection_name,
            count_filter=qdrant_filter,
            exact=exact,
        )

        return count_result.count

    def delete(self, ids: Optional[List[str]] = None) -> int:
        """
        Delete vectors by their IDs or filters.
        
        Args:
            ids: List of vector IDs to delete
            filters: Filters to select vectors to delete
        Returns:
            Number of vectors deleted
        """
        if not ids:
            return 0

        self._client.delete(
            collection_name=self._collection_name,
            points_selector=qmodels.PointIdsList(points=ids),
            wait=True,
        )

        return len(ids)

    def delete_by_filter(self, filters: Dict[str, Any]) -> int:
        """
        Delete vectors matching a filter.
        
        Args:
            filters: Filters to select vectors to delete
            
        Returns:
            Number of vectors deleted
        """
        if not filters:
            return 0

        vectors_count = self.count(filters)

        self._client.delete(
            collection_name=self._collection_name,
            points_selector=qmodels.FilterSelector(filter=self._convert_filters(filters)),
            wait=True,
        )

        return vectors_count

    def delete_by_source_id(self, source_id: str) -> int:
        """
        Delete vectors matching a source ID.
        
        Args:
            source_id: Source ID to delete vectors for
            
        Returns:
            Number of vectors deleted
        """
        return self.delete_by_filter({"metadata.source_id": source_id})

    def _convert_filters(self, filters: Dict[str, Any]) -> qmodels.Filter:
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
                must_conditions.append(
                    qmodels.FieldCondition(
                        key=field,
                        match=qmodels.MatchAny(any=list(value)),
                    )
                )
            else:
                # Handle single value
                must_conditions.append(
                    qmodels.FieldCondition(
                        key=field,
                        match=qmodels.MatchValue(value=value),
                    )
                )

        return qmodels.Filter(must=must_conditions)
