from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import CustomAgentNodeConfig
from .custom_agent import CustomAgentNode
from .identifiers import Identifier


class CustomAgentNodeFactory(BaseFactory[CustomAgentNodeConfig, CustomAgentNode]):
    """
    Factory for creating CustomAgentNode instances.
    """

    def accepts(self, cfg: CustomAgentNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg, **deps):
        try:
            element_deps = deps.get("deps")
            return CustomAgentNode(
                llm=deps.pop("llm"),
                retriever=deps.pop("retriever"),
                tools=deps.pop("tools"),
                mcp_providers=deps.pop("providers"),
                file_retrieve_tool_factory=(
                    element_deps.file_retrieve_tool_factory if element_deps else None
                ),
                system_message=cfg.system_message,
                strategy_type=cfg.strategy_type,
                max_rounds=cfg.max_rounds,
                retries=cfg.retries,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"CustomAgentNodeFactory.create failed: {e}",
                cfg.dict()
            ) from e
