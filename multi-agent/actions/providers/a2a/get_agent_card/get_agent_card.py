from typing import Optional, Dict, Any
from pydantic import HttpUrl
from actions.common.base_action import BaseAction
from actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from elements.providers.a2a_client import A2AClient
from elements.nodes.a2a_agent.identifiers import Identifier
from core.enums import ResourceCategory
from a2a.types import AgentCard


# Input/Output models for this action
class GetAgentCardInput(BaseActionInput):
    """Input for A2A agent card discovery"""
    base_url: HttpUrl
    # bearer_token: Optional[str] = None


class GetAgentCardOutput(BaseActionOutput):
    """Output for A2A agent card discovery"""
    agent_card: Optional[AgentCard] = None


class GetAgentCardAction(BaseAction):
    """
    Discovers agent card from A2A agent endpoint.
    
    Returns the complete AgentCard object from the A2A SDK as-is.
    The agent card contains all agent metadata including identity,
    skills, capabilities, and any other fields defined by the SDK.
    
    Single Responsibility: Only discovers and returns the agent card
    """
    
    uid = "a2a.get_agent_card"
    name = "get_agent_card"
    description = "Retrieve the agent card from an A2A agent endpoint"
    action_type = ActionType.DISCOVERY
    input_schema = GetAgentCardInput
    output_schema = GetAgentCardOutput
    version = "1.0.0"
    tags = {"a2a", "discovery", "agent-card", "skills"}
    elements = {(ResourceCategory.NODE.value, Identifier.TYPE)}
    
    async def execute(self, input_data: GetAgentCardInput, 
                     context: Optional[Dict[str, Any]] = None) -> GetAgentCardOutput:
        """
        Execute agent card discovery asynchronously.
        
        Args:
            input_data: Validated discovery input with base_url and optional bearer_token
            context: Optional execution context
            
        Returns:
            Discovery result with complete agent card
        """
        # Build headers from bearer_token if provided
        headers = None
        # if input_data.bearer_token:
        #     headers = {"Authorization": f"Bearer {input_data.bearer_token}"}
        
        try:
            # Create A2A client and fetch agent card
            async with A2AClient(
                base_url=input_data.base_url,
                headers=headers
            ) as client:
                agent_card = client.agent_card
            
            # Return the complete agent card as-is
            return GetAgentCardOutput(
                success=True,
                message=f"Successfully retrieved agent card for '{agent_card.name}'",
                agent_card=agent_card
            )
            
        except Exception as e:
            return GetAgentCardOutput(
                success=False,
                message=f"Failed to retrieve agent card: {str(e)}",
                agent_card=None
            )
