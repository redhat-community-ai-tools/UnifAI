from mas.elements.nodes.common.base_config import NodeBaseConfig
from pydantic import Field
from typing import Optional, List, Literal
from .identifiers import Identifier
from mas.core.ref.models import LLMRef, RetrieverRef, ToolRef, ProviderRef
from mas.elements.nodes.common.agent.constants import StrategyType
from mas.core.field_hints import ApiHint, HintType, SelectionType, CardHint
from mas.core.hitl.models import HITLMode


class CustomAgentNodeConfig(NodeBaseConfig):
    """
    Custom agent node with full override capabilities.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    llm: LLMRef = Field(
        description="LLM Ref UID to use",
        json_schema_extra=ApiHint(
            endpoint="/resources/resource.validate",
            method="POST",
            hint_type=HintType.VALIDATE,
            selection_type=SelectionType.AUTOMATIC,
            dependencies={"llm": "resourceId"},
            field_mapping="is_valid"
        ).to_hints()
    )
    retriever: Optional[RetrieverRef] = Field(None, description="Retriever key to use")
    tools: Optional[List[ToolRef]] = Field(default_factory=list, description="List of tool keys")
    providers: Optional[List[ProviderRef]] = Field(
        default_factory=list,
        description="List of MCP Provider Refs",
        json_schema_extra=ApiHint(
            endpoint="/resources/resources.validate",
            method="POST",
            hint_type=HintType.VALIDATE,
            selection_type=SelectionType.AUTOMATIC,
            dependencies={"providers": "resourceIds"},
            field_mapping="is_valid"
        ).to_hints()
    )
    system_message: str = Field(
        "",
        description="Custom system prompt",
        json_schema_extra=CardHint(contexts=["builtin", "custom"]).to_hints(),
    )
    strategy_type: str = Field(default=StrategyType.REACT.value, description="Agent strategy type")
    max_rounds: Optional[int] = Field(default=100, description="Maximum number of agent execution rounds")
    hitl_mode: HITLMode = Field(
        default=HITLMode.SKIP,
        description="HITL approval mode: ask (always), skip (never), dynamic (runtime flag)",
    )
