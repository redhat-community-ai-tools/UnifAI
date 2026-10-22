"""Default adapters of the memory tool: MongoDB text store, Qdrant index, embedding service client.

Third-party clients are imported lazily so that the element can be discovered
without the optional ``memory`` dependencies installed.
"""
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class MongoMemoryTextStore:
    def __init__(self, db_name: str, coll_name: str, mongo_url: Optional[str] = None) -> None:
        import pymongo
        from global_utils.utils.util import get_mongo_url

        self._col = pymongo.MongoClient(mongo_url or get_mongo_url())[db_name][coll_name]
        self._col.create_index([("scope_id", 1), ("memory_id", 1)], unique=True)
        self._col.create_index([("scope_id", 1), ("created_at", -1)])

    def insert_if_absent(self, scope_id: str, memory_id: str, text: str, kind: str) -> bool:
        result = self._col.update_one(
            {"scope_id": scope_id, "memory_id": memory_id},
            {"$setOnInsert": {
                "scope_id": scope_id, "memory_id": memory_id, "text": text, "kind": kind,
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
        return result.upserted_id is not None

    def get_many(self, scope_id: str, memory_ids: List[str]) -> List[dict]:
        return list(self._col.find({"scope_id": scope_id, "memory_id": {"$in": memory_ids}}, {"_id": 0}))

    def list_recent(self, scope_id: str, limit: int) -> List[dict]:
        return list(self._col.find({"scope_id": scope_id}, {"_id": 0}).sort("created_at", -1).limit(limit))


def _point_id(scope_id: str, memory_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"memory://{scope_id}/{memory_id}"))


class QdrantMemoryIndex:
    def __init__(self, collection: str, dim: int, url: Optional[str] = None) -> None:
        import qdrant_client
        from qdrant_client.http import models as qmodels
        self._models = qmodels
        self._collection = collection
        self._client = qdrant_client.QdrantClient(url=url or f"http://{os.getenv('QDRANT_IP', '0.0.0.0')}:{os.getenv('QDRANT_PORT', '6333')}")
        if not self._client.collection_exists(collection):
            self._client.create_collection(
                collection_name=collection,
                vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
            )
            self._client.create_payload_index(
                collection_name=collection, field_name="scope_id",
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )

    def upsert(self, scope_id: str, memory_id: str, vector: List[float]) -> None:
        self._client.upsert(
            collection_name=self._collection,
            points=[self._models.PointStruct(
                id=_point_id(scope_id, memory_id), vector=vector,
                payload={"scope_id": scope_id, "memory_id": memory_id},
            )],
        )

    def search(self, scope_id: str, vector: List[float], top_k: int, min_score: float) -> List[Tuple[str, float]]:
        scope_filter = self._models.Filter(must=[
            self._models.FieldCondition(key="scope_id", match=self._models.MatchValue(value=scope_id)),
        ])
        result = self._client.query_points(
            collection_name=self._collection, query=vector, query_filter=scope_filter,
            limit=top_k, score_threshold=min_score or None, with_payload=True,
        )
        return [(p.payload["memory_id"], p.score) for p in result.points]


class ServiceEmbedder:
    """Embeds text through the shared embedding service client.

    Defaults come from the same environment variables (and fall-backs) the RAG
    service reads, so both embed with the same endpoint and model.
    """

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None, timeout: Optional[int] = None) -> None:
        from global_utils.embedding import EmbeddingClient, EmbeddingService

        client = EmbeddingClient(
            base_url=base_url or os.getenv("EMBEDDING_SERVICE_URL", "http://embedding-service:5002"),
            timeout=timeout or int(os.getenv("EMBEDDING_SERVICE_TIMEOUT", "60")),
        )
        self._service = EmbeddingService(
            client, model_name=model or os.getenv("EMBEDDING_SERVICE_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        )

    def embed(self, text: str) -> List[float]:
        return self._service.generate_embeddings([text])[0]
