from typing import Literal, Optional

from pydantic import Field

from mas.elements.tools.common.base_config import BaseToolConfig
from .identifiers import Identifier


class MemoryToolConfig(BaseToolConfig):
    """Configuration of the scoped memory tool.

    ``scope_id`` is fixed by the blueprint (typically through a placeholder
    resolved from the run context, such as ``{project_id}``) and is never
    taken from the model's arguments, so an agent cannot read or write the
    memory of another scope.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
    scope_id: str = Field(
        ..., min_length=1,
        description="Identifier of the memory scope (e.g. a project id). Entries are never shared across scopes.",
    )
    mongo_db: str = Field("UnifAI", description="MongoDB database holding the memory texts")
    facts_collection: str = Field("facts", description="MongoDB collection holding the structured facts")
    author: Optional[str] = Field(None, description="Optional author recorded as provenance on every write")
    classification: Optional[str] = Field(None, description="Optional data classification recorded as provenance on every write")
    mongo_collection: str = Field("memories", description="MongoDB collection holding the memory texts")
    qdrant_collection: str = Field("memories", description="Qdrant collection holding the memory embeddings")
    embedding_service_url: Optional[str] = Field(
        None, description="Embedding service base URL; defaults to the EMBEDDING_SERVICE_URL environment variable, as in the RAG service",
    )
    embedding_model: Optional[str] = Field(
        None, description="Embedding model name; defaults to the EMBEDDING_SERVICE_MODEL environment variable, as in the RAG service",
    )
    embedding_dim: int = Field(384, gt=0, description="Dimension of the embedding vectors")
    top_k: int = Field(5, gt=0, le=50, description="Default number of memories returned by a read")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity score for a read result")
