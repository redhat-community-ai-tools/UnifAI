"""Bootstrap layer - Composition root for dependency injection and factory wiring."""

from bootstrap.factories import EmbeddingGeneratorFactory, VectorRepositoryFactory
from bootstrap.app_container import (
    # Infrastructure
    mongo_client,
    # Repositories
    pipeline_repository,
    data_source_repository,
    monitoring_repository,
    vector_repository,
    # Processors
    slack_processor,
    document_processor,
    # Chunkers
    slack_chunker,
    pdf_chunker,
    # Services
    pipeline_service,
    monitoring_service,
    # Embedding
    embedding_generator,
    # Utilities
    clear_all_caches,
)

__all__ = [
    # Factories
    "EmbeddingGeneratorFactory",
    "VectorRepositoryFactory",
    # Container - Infrastructure
    "mongo_client",
    # Container - Repositories
    "pipeline_repository",
    "data_source_repository",
    "monitoring_repository",
    "vector_repository",
    # Container - Processors
    "slack_processor",
    "document_processor",
    # Container - Chunkers
    "slack_chunker",
    "pdf_chunker",
    # Container - Services
    "pipeline_service",
    "monitoring_service",
    # Container - Embedding
    "embedding_generator",
    # Container - Utilities
    "clear_all_caches",
]

