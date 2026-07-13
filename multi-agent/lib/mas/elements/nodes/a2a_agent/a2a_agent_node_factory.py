"""
A2A Agent Node Factory

Resolves authentication through the credential store (via auth_credential)
for registry-based auth methods (SSO servers), or from the raw bearer_token
for manually-entered access tokens.
"""

from typing import Any, Optional

from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from mas.core.auth.credentials.credential import AuthCredential
from .config import A2AAgentNodeConfig
from .a2a_agent_node import A2AAgentNode
from .identifiers import Identifier


class A2AAgentNodeFactory(BaseFactory[A2AAgentNodeConfig, A2AAgentNode]):
    """
    Factory for creating A2A Agent Node instances.

    Dependencies injected at session-build time:
    - retriever: Optional retriever instance (resolved from RetrieverRef)
    - auth_credential: Optional AuthCredential (resolved from CredentialStore
      via NodeBuilder when server_identifier is set)
    """

    def accepts(self, cfg: A2AAgentNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: A2AAgentNodeConfig, **deps) -> A2AAgentNode:
        try:
            auth_credential: Optional[AuthCredential] = deps.pop("auth_credential", None)
            retriever = deps.pop("retriever")

            bearer_token = None
            if not auth_credential and cfg.auth_method == "access_token" and cfg.bearer_token:
                bearer_token = cfg.bearer_token

            return A2AAgentNode(
                base_url=cfg.base_url,
                agent_card=cfg.agent_card,
                bearer_token=bearer_token,
                auth_credential=auth_credential,
                retriever=retriever,
                retries=cfg.retries,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"A2AAgentNodeFactory.create failed: {e}",
                cfg.model_dump()
            ) from e
