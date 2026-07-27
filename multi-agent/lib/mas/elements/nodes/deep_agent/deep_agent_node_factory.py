from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import DeepAgentNodeConfig
from .deep_agent_node import DeepAgentNode
from .identifiers import Identifier


class DeepAgentNodeFactory(BaseFactory[DeepAgentNodeConfig, DeepAgentNode]):
    """Factory for creating ``DeepAgentNode`` instances from configuration.

    HITL gate/policy are NOT passed at construction time — they
    are injected at execution time via ``NodeRuntimeBinder`` using
    the ``SupportsHITL`` protocol setters on the node.
    """

    def accepts(self, cfg: DeepAgentNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: DeepAgentNodeConfig, **deps) -> DeepAgentNode:
        try:
            element_deps = deps.pop("deps", None)
            execution_holder = element_deps.execution_ctx if element_deps else None
            platform = element_deps.platform_config if element_deps else None
            shared_storage = platform.shared_storage if platform else "/app/shared"

            return DeepAgentNode(
                llm=deps.pop("llm"),
                retriever=deps.pop("retriever"),
                tools=deps.pop("tools"),
                mcp_providers=deps.pop("providers"),
                sandbox=deps.pop("sandbox", None),
                system_message=cfg.system_message,
                cwd=cfg.cwd,
                env_vars=cfg.env_vars,
                execution_holder=execution_holder,
                shared_storage=shared_storage,
                retries=cfg.retries,
                hitl_mode=cfg.hitl_mode,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"DeepAgentNodeFactory.create failed: {e}",
                cfg.dict(),
            ) from e
