"""
A2A Agent Node Factory
"""

from elements.common.base_factory import BaseFactory
from elements.common.exceptions import PluginConfigurationError
from .config import A2AAgentNodeConfig
from .a2a_agent_node import A2AAgentNode
from .identifiers import Identifier


class A2AAgentNodeFactory(BaseFactory[A2AAgentNodeConfig, A2AAgentNode]):
    """
    Factory for creating A2A Agent Node instances.
    
    Creates node with A2A provider initialized from config.
    Dependencies injected:
    - retriever: Optional retriever instance (resolved from RetrieverRef)
    """

    def accepts(self, cfg: A2AAgentNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: A2AAgentNodeConfig, **deps):
        """
        Create A2A Agent Node from configuration.
        
        Node creates its own A2A provider from base_url and agent_card.
        
        Args:
            cfg: Validated configuration
            deps: Resolved dependencies
                - retriever: Optional retriever
                
        Returns:
            Initialized A2AAgentNode
            
        Raises:
            PluginConfigurationError: If creation fails
        """
        try:
            return A2AAgentNode(
                base_url=cfg.base_url,
                agent_card=cfg.agent_card,
                bearer_token=cfg.bearer_token,
                retriever=deps.pop("retriever"),
                retries=cfg.retries,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"A2AAgentNodeFactory.create failed: {e}",
                cfg.dict()
            ) from e

