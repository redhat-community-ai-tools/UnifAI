from mas.elements.common.base_factory import BaseFactory
from mas.elements.common.exceptions import PluginConfigurationError
from .config import MemoryExtractorNodeConfig
from .identifiers import Identifier
from .memory_extractor import MemoryExtractorNode


class MemoryExtractorNodeFactory(BaseFactory[MemoryExtractorNodeConfig, MemoryExtractorNode]):
    """Builds a MemoryExtractorNode from its resolved llm, memory tool and optional local llm."""

    def accepts(self, cfg: MemoryExtractorNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: MemoryExtractorNodeConfig, **deps) -> MemoryExtractorNode:
        try:
            ctx = deps.get("deps")
            return MemoryExtractorNode(
                llm=deps["llm"],
                memory=deps["memory"],
                local_llm=deps.get("local_llm"),
                classification=cfg.classification,
                restricted_classifications=cfg.restricted_classifications,
                execution_holder=getattr(ctx, "execution_ctx", None),
                retries=cfg.retries,
            )
        except Exception as exc:
            raise PluginConfigurationError(
                f"MemoryExtractorNodeFactory.create failed: {exc}",
                cfg.dict(),
            ) from exc
