from typing import Literal, Optional
from pydantic import Field
from mas.elements.nodes.common.base_config import NodeBaseConfig
from mas.core.ref.models import LLMRef
from mas.core.field_hints import CardHint, CardContext
from .identifiers import Identifier


class MockAgentNodeConfig(NodeBaseConfig):
    """
    Allows overriding only the LLM key for the mock agent node.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    llm: Optional[LLMRef] = Field(
        None,
        description="LLM key to use for the mock agent",
        title="LLM",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    echo_message: Optional[str] = Field(
        None,
        description="Optional fixed message to return",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
