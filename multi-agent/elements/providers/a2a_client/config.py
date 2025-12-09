"""
A2A Provider Configuration
"""

from typing import Literal, Optional, Dict
from pydantic import Field, HttpUrl
from elements.providers.common.base_config import ProviderBaseConfig
from a2a.types import AgentCard
from .identifiers import Identifier


class A2AProviderConfig(ProviderBaseConfig):
    """
    A2A Provider Configuration.
    
    Simple configuration with just base_url and optional agent_card.
    """
    
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    
    base_url: HttpUrl = Field(
        description="Base URL of the A2A agent (e.g., http://localhost:10000)"
    )
    
    agent_card: Optional[AgentCard] = Field(
        default=None,
        description="Pre-fetched agent card (optional, will be fetched if not provided)"
    )
    
    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional HTTP headers for authentication (e.g., {'Authorization': 'Bearer <token>'})"
    )
