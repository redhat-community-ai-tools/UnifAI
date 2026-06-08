from pydantic import Field, HttpUrl
from global_utils.config.config import SharedConfig


class RagProviderConfig(SharedConfig):
    """
    Infrastructure config for RAG service client.

    Unlike other providers, RAG is internal (not in the ElementRegistry or
    UI catalog), so it inherits SharedConfig instead of ProviderBaseConfig —
    fields are overridable via env vars / ``.env``.
    """
    base_url: HttpUrl = Field(
        default="http://unifai-rag-server:13456",
        description="Base URL of the RAG service",
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

