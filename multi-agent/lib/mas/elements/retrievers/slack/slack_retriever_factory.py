from typing import Any
from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from mas.core.element_deps import ElementBuildContext
from .config import SlackRetrieverConfig
from .slack_retriever import SlackRetriever
from .identifiers import Identifier


class SlackRetrieverFactory(BaseFactory[SlackRetrieverConfig, SlackRetriever]):
    def accepts(self, cfg: SlackRetrieverConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: SlackRetrieverConfig, **kwargs: Any) -> SlackRetriever:
        deps: ElementBuildContext | None = kwargs.get("deps")
        try:
            return SlackRetriever(
                api_url=cfg.api_url,
                top_k_results=cfg.top_k_results,
                threshold=cfg.threshold,
                identity=deps.execution_ctx if deps else None,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"SlackRetrieverFactory.create() failed: {e}", cfg.dict()
            ) from e
