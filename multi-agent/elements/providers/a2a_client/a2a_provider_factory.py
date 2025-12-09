"""
A2A Provider Factory
"""

from typing import Any

from elements.common.base_factory import BaseFactory
from elements.common.exceptions import PluginConfigurationError
from elements.providers.a2a_client.config import A2AProviderConfig
from elements.providers.a2a_client.provider import A2AProvider
from elements.providers.a2a_client.identifiers import Identifier


class A2AProviderFactory(BaseFactory[A2AProviderConfig, A2AProvider]):
    """
    Factory for creating A2A Provider instances from configuration.
    """

    def accepts(self, cfg: A2AProviderConfig, element_type: str) -> bool:
        """Check if this factory accepts the given config type."""
        return element_type == Identifier.TYPE

    def create(self, cfg: A2AProviderConfig, **kwargs: Any) -> A2AProvider:
        """
        Create A2AProvider instance (sync).
        
        Args:
            cfg: Validated A2AProviderConfig
            **kwargs: Additional arguments
            
        Returns:
            Initialized A2AProvider
            
        Raises:
            PluginConfigurationError: If creation fails
        """
        try:
            return A2AProvider.create_sync(
                base_url=cfg.base_url,
                agent_card=cfg.agent_card,
                headers=cfg.headers,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"A2AProvider.create() failed: {e}",
                cfg.model_dump()
            ) from e

    async def create_async(self, cfg: A2AProviderConfig, **kwargs: Any) -> A2AProvider:
        """
        Create A2AProvider instance (async).
        
        Args:
            cfg: Validated A2AProviderConfig
            **kwargs: Additional arguments
            
        Returns:
            Initialized A2AProvider
            
        Raises:
            PluginConfigurationError: If creation fails
        """
        try:
            return await A2AProvider.create(
                base_url=cfg.base_url,
                agent_card=cfg.agent_card,
                headers=cfg.headers,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"A2AProvider.create_async() failed: {e}",
                cfg.model_dump()
            ) from e
