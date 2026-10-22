from typing import Any

from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import MemoryToolConfig
from .identifiers import Identifier
from .memory import MemoryTool


class MemoryToolFactory(BaseFactory[MemoryToolConfig, MemoryTool]):

    def accepts(self, cfg: MemoryToolConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: MemoryToolConfig, **kwargs: Any) -> MemoryTool:
        """Build the tool. ``store``, ``facts``, ``index`` and ``embedder`` may be injected (tests)."""
        try:
            store = kwargs.get("store")
            index = kwargs.get("index")
            embedder = kwargs.get("embedder")
            facts = kwargs.get("facts")
            if store is None or facts is None or index is None or embedder is None:
                from .adapters import MongoFactStore, MongoMemoryTextStore, QdrantMemoryIndex, ServiceEmbedder
                facts = facts or MongoFactStore(cfg.mongo_db, cfg.facts_collection)
                store = store or MongoMemoryTextStore(cfg.mongo_db, cfg.mongo_collection)
                index = index or QdrantMemoryIndex(cfg.qdrant_collection, cfg.embedding_dim)
                embedder = embedder or ServiceEmbedder(cfg.embedding_service_url, cfg.embedding_model)
            return MemoryTool(
                cfg.scope_id, store, index, embedder, top_k=cfg.top_k, min_score=cfg.min_score,
                facts=facts, author=cfg.author, classification=cfg.classification,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"MemoryToolFactory.create() failed: {e}",
                cfg.dict(),
            ) from e
