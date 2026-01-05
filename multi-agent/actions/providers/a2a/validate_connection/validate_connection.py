"""
A2A validate_connection action.

Validates A2A agent connection reachability.
"""

import anyio
import time
from typing import Optional, Dict, Any
from pydantic import HttpUrl
from actions.common.base_action import BaseAction
from actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from elements.providers.a2a_client import A2AClient
from elements.nodes.a2a_agent.identifiers import Identifier
from core.enums import ResourceCategory


# Input/Output models for this action
class ValidateConnectionInput(BaseActionInput):
    """Input for A2A connection validation"""
    base_url: HttpUrl
    # bearer_token: Optional[str] = None


class ValidateConnectionOutput(BaseActionOutput):
    """Output for A2A connection validation"""
    is_reachable: bool = False
    response_time_ms: float = 0.0


class ValidateConnectionAction(BaseAction):
    """
    Validates A2A agent connection.
    
    This action tests connectivity by attempting to fetch the agent card
    from the A2A endpoint. If successful, the agent is considered reachable.
    
    Single Responsibility: Only validates connection reachability
    """
    
    uid = "a2a.validate_connection"
    name = "validate_connection"
    description = "Validate that the A2A agent endpoint is reachable and responding"
    action_type = ActionType.VALIDATION
    input_schema = ValidateConnectionInput
    output_schema = ValidateConnectionOutput
    version = "1.0.0"
    tags = {"a2a", "validation", "connectivity"}
    elements = {(ResourceCategory.NODE.value, Identifier.TYPE)}
    
    async def execute(
        self,
        input_data: ValidateConnectionInput, 
        context: Optional[Dict[str, Any]] = None
    ) -> ValidateConnectionOutput:
        """
        Execute connection validation.
        
        Args:
            input_data: Validated connection input with base_url
            context: Optional execution context
            
        Returns:
            Validation result with connection status and timing
        """
        start_time = time.time()
        
        # Build headers from bearer_token if provided
        headers = None
        # if input_data.bearer_token:
        #     headers = {"Authorization": f"Bearer {input_data.bearer_token}"}
        
        try:
            with anyio.fail_after(10.0):
                async with A2AClient(
                    base_url=input_data.base_url,
                    headers=headers
                ) as client:
                    # Agent card is fetched during __aenter__
                    # Just confirm we can access it (connection successful)
                    _ = client.agent_card
            
            response_time = (time.time() - start_time) * 1000
            
            return ValidateConnectionOutput(
                success=True,
                message="Connection successful",
                is_reachable=True,
                response_time_ms=response_time
            )
            
        except TimeoutError:
            return ValidateConnectionOutput(
                success=False,
                message="Connection timeout - agent may be unreachable",
                is_reachable=False,
                response_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return ValidateConnectionOutput(
                success=False,
                message=f"Connection failed: {str(e)}",
                is_reachable=False,
                response_time_ms=(time.time() - start_time) * 1000
            )
