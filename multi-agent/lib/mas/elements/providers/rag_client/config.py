import os
from typing import Literal
from pydantic import Field, HttpUrl
from mas.elements.providers.common.base_config import ProviderBaseConfig
from mas.core.field_hints import ActionHint, HintType
from .identifiers import Identifier

_DEFAULT_RAG_URL = os.environ.get("RAG_BASE_URL", "http://unifai-rag-server:13456")


class RagProviderConfig(ProviderBaseConfig):
    """
    Configuration for RAG service client.
    Connects to a RAG server for vector database queries and document retrieval.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE

    base_url: HttpUrl = Field(
        default=_DEFAULT_RAG_URL,
        description="Base URL of the RAG service",
        json_schema_extra=ActionHint(
            action_uid="rag.validate_connection",
            hint_type=HintType.VALIDATE,
            field_mapping="is_reachable"
        ).to_hints()
    )

    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of top results to return from vector queries"
    )

    timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Request timeout in seconds"
    )

