from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from mas.core.auth.credentials.credential import AuthCredential
from .config import McpProviderConfig
from .mcp_provider import McpProvider
from .identifiers import Identifier

logger = logging.getLogger(__name__)


class McpProviderFactory(BaseFactory[McpProviderConfig, McpProvider]):

    def accepts(self, cfg: McpProviderConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def _build_headers(self, cfg: McpProviderConfig) -> Optional[Dict[str, str]]:
        headers = dict(cfg.additional_headers) if cfg.additional_headers else {}
        if cfg.bearer_token:
            headers["Authorization"] = f"Bearer {cfg.bearer_token}"
        return headers or None

    def create(self, cfg: McpProviderConfig, **kwargs: Any) -> McpProvider:
        try:
            auth = kwargs.get("auth_credential")
            headers = self._build_headers(cfg)

            return McpProvider(
                mcp_url=cfg.mcp_url,
                tool_names=cfg.tool_names,
                headers=headers,
                transport_type=cfg.transport_type,
                auth=auth,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"McpProvider.create() failed: {e}", cfg.dict(),
            ) from e

    async def create_async(self, cfg: McpProviderConfig, **kwargs: Any) -> McpProvider:
        try:
            auth = kwargs.get("auth_credential")
            headers = self._build_headers(cfg)

            return await McpProvider.create_async(
                mcp_url=cfg.mcp_url,
                tool_names=cfg.tool_names,
                headers=headers,
                transport_type=cfg.transport_type,
                auth=auth,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"McpProvider.create_async() failed: {e}", cfg.dict(),
            ) from e
