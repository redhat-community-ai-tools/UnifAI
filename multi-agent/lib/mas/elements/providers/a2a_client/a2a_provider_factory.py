"""
A2A Provider Factory
"""

from typing import Any, Dict, Optional

from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from mas.core.auth.credentials.models import StaticAuthMethod
from mas.elements.providers.a2a_client.config import A2AProviderConfig
from mas.elements.providers.a2a_client.provider import A2AProvider
from mas.elements.providers.a2a_client.identifiers import Identifier


class A2AProviderFactory(BaseFactory[A2AProviderConfig, A2AProvider]):
    """
    Factory for creating A2A Provider instances from configuration.

    Session build may inject ``auth_credential`` via ProviderBuilder when
    ``server_identifier`` is a registry SSO server (parity with MCP).
    """

    def accepts(self, cfg: A2AProviderConfig, element_type: str) -> bool:
        """Check if this factory accepts the given config type."""
        return element_type == Identifier.TYPE

    @staticmethod
    def _resolve_headers(cfg: A2AProviderConfig) -> Optional[Dict[str, str]]:
        """Build static HTTP headers from config auth fields (not SSO store)."""
        headers: Dict[str, str] = (
            dict(cfg.additional_headers) if cfg.additional_headers else {}
        )

        if cfg.credential_token:
            headers["Authorization"] = f"Bearer {cfg.credential_token}"
        elif cfg.auth_method == StaticAuthMethod.ACCESS_TOKEN and cfg.bearer_token:
            headers["Authorization"] = f"Bearer {cfg.bearer_token}"

        return headers or None

    def create(self, cfg: A2AProviderConfig, **kwargs: Any) -> A2AProvider:
        """
        Create A2AProvider instance (sync).

        Raises:
            PluginConfigurationError: If creation fails
        """
        try:
            auth = kwargs.pop("auth_credential", None)
            return A2AProvider.create_sync(
                base_url=cfg.base_url,
                agent_card=cfg.agent_card,
                headers=self._resolve_headers(cfg),
                auth=auth,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"A2AProvider.create() failed: {e}",
                cfg.model_dump()
            ) from e

    async def create_async(self, cfg: A2AProviderConfig, **kwargs: Any) -> A2AProvider:
        """
        Create A2AProvider instance (async).

        Raises:
            PluginConfigurationError: If creation fails
        """
        try:
            auth = kwargs.pop("auth_credential", None)
            return await A2AProvider.create(
                base_url=cfg.base_url,
                agent_card=cfg.agent_card,
                headers=self._resolve_headers(cfg),
                auth=auth,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"A2AProvider.create_async() failed: {e}",
                cfg.model_dump()
            ) from e
