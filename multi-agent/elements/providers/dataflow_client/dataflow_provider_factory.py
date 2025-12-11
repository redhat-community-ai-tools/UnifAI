"""
Dataflow Provider Factory
"""
from typing import Any

from elements.common.base_factory import BaseFactory
from elements.common.exceptions import PluginConfigurationError
from .config import DataflowProviderConfig
from .dataflow_provider import DataflowProvider
from .identifiers import Identifier


class DataflowProviderFactory(BaseFactory[DataflowProviderConfig, DataflowProvider]):
    """
    Factory for creating Dataflow Provider instances from configuration.
    """

    def accepts(self, cfg: DataflowProviderConfig, element_type: str) -> bool:
        """Check if this factory accepts the given config type."""
        return element_type == Identifier.TYPE

    def create(self, cfg: DataflowProviderConfig, **kwargs: Any) -> DataflowProvider:
        """
        Create DataflowProvider instance.

        Args:
            cfg: Validated DataflowProviderConfig
            **kwargs: Additional arguments

        Returns:
            Initialized DataflowProvider

        Raises:
            PluginConfigurationError: If creation fails
        """
        try:
            return DataflowProvider(
                base_url=cfg.base_url,
                top_k=cfg.top_k,
                timeout=cfg.timeout,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"DataflowProvider creation failed: {e}",
                cfg.model_dump()
            ) from e

