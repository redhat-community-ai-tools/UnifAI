"""
A2A Provider Package.

Provides clean interface for communicating with A2A (Agent-to-Agent) protocol agents.
Uses official a2a-sdk internally with extensible handler system.
"""

from elements.providers.a2a_client.provider import A2AProvider, A2ATaskError, A2ATimeoutError
from elements.providers.a2a_client.client import A2AClient, A2AClientError, A2AConnectionError
from elements.providers.a2a_client.converter import A2AConverter, ConversionResult, FileInfo
from elements.providers.a2a_client.result import A2AResult, ResultKind
from elements.providers.a2a_client.config import A2AProviderConfig
from elements.providers.a2a_client.identifiers import Identifier, META
from elements.providers.a2a_client.a2a_provider_factory import A2AProviderFactory

from elements.providers.a2a_client.handlers import (
    BaseHandler,
    TaskHandler,
    MessageHandler,
    StatusEventHandler,
    ArtifactEventHandler,
)

__all__ = [
    "A2AProvider",
    "A2AProviderFactory",
    "A2AClient",
    "A2AClientError",
    "A2AConnectionError",
    "A2ATaskError",
    "A2ATimeoutError",
    "A2AConverter",
    "ConversionResult",
    "FileInfo",
    "A2AResult",
    "ResultKind",
    "A2AProviderConfig",
    "Identifier",
    "META",
    "BaseHandler",
    "TaskHandler",
    "MessageHandler",
    "StatusEventHandler",
    "ArtifactEventHandler",
]
