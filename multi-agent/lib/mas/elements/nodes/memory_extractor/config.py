from typing import List, Literal, Optional

from pydantic import Field

from mas.core.ref.models import LLMRef, ToolRef
from mas.elements.nodes.common.base_config import NodeBaseConfig
from .identifiers import Identifier

DEFAULT_RESTRICTED = ["restricted", "confidential", "secret"]


class MemoryExtractorNodeConfig(NodeBaseConfig):
    """Extracts facts and memories from the session transcript and stores them through a memory tool.

    The memory tool carries the scope and the access block; the node never chooses a scope.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    llm: LLMRef = Field(description="LLM used to extract the memories", title="LLM")
    memory: ToolRef = Field(
        description="Memory tool (scope and access block are configured on the tool)",
        title="Memory tool",
    )
    classification: Optional[str] = Field(
        None,
        description=(
            "Classification of the transcript. A restricted classification is only sent to `local_llm`; "
            "the node refuses (writes nothing) when none is configured."
        ),
    )
    local_llm: Optional[LLMRef] = Field(
        None,
        description="LLM allowed to see restricted classifications (e.g. a model hosted in the cluster)",
        title="Local LLM",
    )
    restricted_classifications: List[str] = Field(
        default_factory=lambda: list(DEFAULT_RESTRICTED),
        description="Classifications (case-insensitive) that may only be processed by `local_llm`",
    )
