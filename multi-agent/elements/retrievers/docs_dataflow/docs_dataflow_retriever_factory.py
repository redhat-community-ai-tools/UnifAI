from typing import Any
from elements.common.base_factory import BaseFactory
from elements.common.exceptions import PluginConfigurationError
from .config import DocsDataflowRetrieverConfig
from .docs_dataflow_retriever import DocsDataflowRetriever
from .identifiers import Identifier


class DocsDataflowRetrieverFactory(BaseFactory[DocsDataflowRetrieverConfig, DocsDataflowRetriever]):
    """
    Factory for creating DocsDataflowRetriever instances from configuration.
    """

    def accepts(self, cfg: DocsDataflowRetrieverConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: DocsDataflowRetrieverConfig, **kwargs: Any) -> DocsDataflowRetriever:
        try:
            return DocsDataflowRetriever(
                top_k_results=cfg.top_k_results,
                threshold=cfg.threshold,
                timeout=cfg.timeout,
                doc_ids=cfg.doc_ids,
                tags=cfg.tags,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"DocsDataflowRetrieverFactory.create() failed: {e}",
                cfg.model_dump()
            ) from e

