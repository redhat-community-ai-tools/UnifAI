from mas.elements.nodes.common.base_config import NodeBaseConfig
from pydantic import Field
from typing import Dict, Optional, List, Literal
from .identifiers import Identifier
from mas.core.ref.models import LLMRef, RetrieverRef, ToolRef, ProviderRef
from mas.core.field_hints import ApiHint, HiddenHint, HintType, SelectionType
from mas.core.hitl.models import HITLMode


class DeepAgentNodeConfig(NodeBaseConfig):
    """
    Deep Agent node powered by LangChain Deep Agents.

    Delegates execution to a compiled Deep Agent graph that provides
    built-in planning (todos), context management, and a general-purpose
    subagent for automatic task delegation.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE

    llm: LLMRef = Field(
        description="LLM Ref UID to use as the Deep Agent's model",
        json_schema_extra=ApiHint(
            endpoint="/resources/resource.validate",
            method="POST",
            hint_type=HintType.VALIDATE,
            selection_type=SelectionType.AUTOMATIC,
            dependencies={"llm": "resourceId"},
            field_mapping="is_valid"
        ).to_hints()
    )

    retriever: Optional[RetrieverRef] = Field(
        None,
        description="Retriever for context augmentation (optional)"
    )

    tools: Optional[List[ToolRef]] = Field(
        default_factory=list,
        description="List of tool keys"
    )

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
        description="System prompt for the Deep Agent"
    )

    # --- Backend / Environment ---

    cwd: Optional[str] = Field(
        default=None,
        description="Working directory override (defaults to shared_storage/{session}/{node})",
        json_schema_extra=HiddenHint(
            reason="Advanced: override working directory"
        ).to_hints()
    )

    env_vars: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional environment variables for the deep agent session",
        json_schema_extra=HiddenHint(
            reason="Advanced: custom environment variables"
        ).to_hints()
    )

    hitl_mode: HITLMode = Field(
        default=HITLMode.SKIP,
        description="HITL approval mode: ask (always), skip (never), dynamic (runtime flag)",
    )
