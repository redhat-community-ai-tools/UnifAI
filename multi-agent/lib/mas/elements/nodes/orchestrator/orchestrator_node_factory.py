from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import OrchestratorNodeConfig
from .orchestrator_node import OrchestratorNode
from .identifiers import Identifier


class OrchestratorNodeFactory(BaseFactory[OrchestratorNodeConfig, OrchestratorNode]):
    """
    Factory for creating OrchestratorNode instances.
    
    Handles dependency injection and configuration validation
    for orchestrator nodes.
    """

    def accepts(self, cfg: OrchestratorNodeConfig, element_type: str) -> bool:
        """Check if this factory can create the requested element type."""
        return element_type == Identifier.TYPE

    def create(self, cfg: OrchestratorNodeConfig, **deps) -> OrchestratorNode:
        """
        Create an OrchestratorNode instance.
        
        Args:
            cfg: Orchestrator node configuration
            **deps: Injected dependencies (llm, tools)
            
        Returns:
            Configured OrchestratorNode instance
            
        Raises:
            PluginConfigurationError: If creation fails
        """
        try:
            element_deps = deps.pop("deps", None)
            tracing_service = element_deps.tracing_service if element_deps else None

            return OrchestratorNode(
                llm=deps.pop("llm"),
                tools=deps.pop("tools", []),
                system_message=cfg.system_message,
                max_rounds=cfg.max_rounds,
                retries=cfg.retries,
                tracing_service=tracing_service,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"OrchestratorNodeFactory.create failed: {e}",
                cfg.dict()
            ) from e


