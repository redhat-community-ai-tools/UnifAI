"""
Dataflow Client Provider

This package provides synchronous Dataflow service integration for vector database
queries and document retrieval.
"""

from .dataflow_provider import DataflowProvider
from .dataflow_provider_factory import DataflowProviderFactory
from .client import DataflowClient, DataflowClientError, DataflowConnectionError
from .config import DataflowProviderConfig
from .identifiers import Identifier, META
from .models import (
    TagOption,
    AvailableTagsResponse,
    DocumentInfo,
    AvailableDocsResponse,
    QueryMatchResult,
    QueryMatchResponse,
    HealthResponse,
)

__all__ = [
    "DataflowProvider",
    "DataflowProviderFactory",
    "DataflowClient",
    "DataflowClientError",
    "DataflowConnectionError",
    "DataflowProviderConfig",
    "Identifier",
    "META",
    "TagOption",
    "AvailableTagsResponse",
    "DocumentInfo",
    "AvailableDocsResponse",
    "QueryMatchResult",
    "QueryMatchResponse",
    "HealthResponse",
]

