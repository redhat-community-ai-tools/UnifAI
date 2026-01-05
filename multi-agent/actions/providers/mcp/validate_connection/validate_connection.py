"""
MCP validate_connection action.

Validates MCP server connection reachability.
"""

import asyncio
import time
from typing import Optional, Dict, Any

from pydantic import HttpUrl

from actions.common.base_action import BaseAction
from actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from elements.providers.mcp_server_client.mcp_server_client import McpServerClient
from elements.providers.mcp_server_client.identifiers import Identifier
from core.enums import ResourceCategory


# Input/Output models for this action
class ValidateConnectionInput(BaseActionInput):
    """Input for MCP connection validation"""
    sse_endpoint: HttpUrl


class ValidateConnectionOutput(BaseActionOutput):
    """Output for MCP connection validation"""
    is_reachable: bool = False
    response_time_ms: float = 0.0


class ValidateConnectionAction(BaseAction):
    """
    Validates MCP server connection.
    
    This action can work with any MCP-compatible element or independently.
    Single Responsibility: Only validates connection reachability
    """
    
    uid = "mcp.validate_connection"
    name = "validate_connection"
    description = "Validate that the MCP server endpoint is reachable and responding"
    action_type = ActionType.VALIDATION
    input_schema = ValidateConnectionInput
    output_schema = ValidateConnectionOutput
    version = "1.0.0"
    tags = {"mcp", "validation", "connectivity"}
    elements = {(ResourceCategory.PROVIDER.value, Identifier.TYPE)}

    def execute_sync(
        self,
        input_data: ValidateConnectionInput,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidateConnectionOutput:
        """
        Override execute_sync to handle MCP library's cancel scope corruption.
        
        The MCP library's streamablehttp_client has a bug where it corrupts
        anyio's cancel scope stack during connection failures. This causes a
        RuntimeError to be raised during the AsyncBridge's portal cleanup -
        AFTER the async code has finished executing.
        
        Because this error occurs outside the async execution context, it cannot
        be caught inside the async execute() method. We must catch it here at
        the sync boundary.
        
        This is a workaround for a third-party library bug, not a flaw in our
        AsyncBridge implementation.
        """
        try:
            return super().execute_sync(input_data, context)
        except RuntimeError as e:
            # Cancel scope errors from MCP library indicate connection failure
            return ValidateConnectionOutput(
                success=False,
                message=f"Connection failed: {e}",
                is_reachable=False,
                response_time_ms=0.0
            )

    async def execute(
        self,
        input_data: ValidateConnectionInput,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidateConnectionOutput:
        """
        Execute connection validation.

        Args:
            input_data: Validated connection input
            context: Optional execution context

        Returns:
            Validation result with connection status and timing
        """
        start_time = time.time()
        
        try:
            # Create client and test connection
            client = McpServerClient(input_data.sse_endpoint)
            
            async with client:
                # Test connection by listing tools with timeout
                await asyncio.wait_for(client.tools.get_tools(), timeout=10.0)
            
            response_time = (time.time() - start_time) * 1000
            
            return ValidateConnectionOutput(
                success=True,
                message="Connection successful",
                is_reachable=True,
                response_time_ms=response_time
            )
            
        except asyncio.TimeoutError:
            return ValidateConnectionOutput(
                success=False,
                message="Connection timeout - server may be unreachable",
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
