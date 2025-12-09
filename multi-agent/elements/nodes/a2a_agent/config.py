"""
A2A Agent Node Configuration
"""

from elements.nodes.common.base_config import NodeBaseConfig
from pydantic import Field, HttpUrl
from typing import Optional, Literal
from a2a.types import AgentCard
from .identifiers import Identifier
from core.ref.models import RetrieverRef
from core.field_hints import ActionHint, HintType, SelectionType, SecretHint


class A2AAgentNodeConfig(NodeBaseConfig):
    """
    A2A Agent Node - delegates work to remote agent via A2A protocol.
    
    Simple configuration with just endpoint and optional retriever.
    The node creates its own A2A provider internally.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE

    base_url: HttpUrl = Field(
        description="Base URL of the A2A agent (e.g., http://localhost:10000)",
        json_schema_extra=ActionHint(
            action_uid="a2a.validate_connection",
            hint_type=HintType.VALIDATE,
            field_mapping="is_reachable"
        ).to_hints()
    )

    bearer_token: Optional[str] = Field(
        default=None,
        description="Bearer token for authentication (will be sent as 'Authorization: Bearer <token>' header)",
        json_schema_extra=SecretHint(
            allow_reveal=True
        ).to_hints()
    )

    agent_card: Optional[AgentCard] = Field(
        default=None,
        description="Pre-fetched agent card (optional, will be fetched if not provided)",
        json_schema_extra=ActionHint(
            action_uid="a2a.get_agent_card",
            hint_type=HintType.POPULATE,
            selection_type=SelectionType.AUTOMATIC,
            field_mapping="agent_card",
            dependencies={
                "base_url": "base_url"            }
        ).to_hints()
    )

    retriever: Optional[RetrieverRef] = Field(
        None,
        description="Retriever for context augmentation (optional)"
    )
