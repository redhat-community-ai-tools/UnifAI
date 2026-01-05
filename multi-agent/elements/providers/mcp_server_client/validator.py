"""
elements/providers/mcp_server_client/validator.py

Validator for MCP Provider - checks endpoint reachability using McpServerClient.
"""

import anyio
from concurrent.futures import CancelledError
from typing import List

from global_utils.utils.async_bridge import get_async_bridge
from elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from elements.providers.mcp_server_client.config import McpProviderConfig
from elements.providers.mcp_server_client.mcp_server_client import McpServerClient


class McpProviderValidator(BaseElementValidator):
    """
    Validates MCP Provider configuration.
    
    Checks:
    - MCP server connectivity
    - Ability to list tools from the server
    """

    def validate(
        self,
        config: McpProviderConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        """
        Validate MCP provider config.
        
        Synchronous method - runs async checks internally using AsyncBridge.
        Returns ValidatorReport (service adds metadata).
        """
        messages: List[ValidationMessage] = []

        try:
            with get_async_bridge() as bridge:
                bridge.run(self._check_connection(config, context, messages))
        except (CancelledError, TimeoutError) as e:
            messages.append(self._error(
                ValidationCode.NETWORK_TIMEOUT.value,
                str(e),
                field="sse_endpoint",
            ))
        except RuntimeError as e:
            # MCP library cancel scope bug - handle here only
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Connection failed: {e}",
                field="sse_endpoint",
            ))

        return self._build_report(messages=messages)

    async def _check_connection(
        self,
        config: McpProviderConfig,
        context: ValidationContext,
        messages: List[ValidationMessage],
    ) -> None:
        """
        Async MCP connection check using McpServerClient.
        
        Uses anyio.fail_after INSIDE the async function for timeout control.
        """
        try:
            with anyio.fail_after(context.timeout_seconds):
                client = McpServerClient(config.sse_endpoint)
                async with client:
                    await client.tools.get_tools()
            
            # Connection successful
            messages.append(self._info(
                "CONNECTION_OK",
                f"Successfully connected to MCP server at {config.sse_endpoint}",
                field="sse_endpoint",
            ))

        except TimeoutError:
            messages.append(self._error(
                ValidationCode.NETWORK_TIMEOUT.value,
                f"Connection timed out after {context.timeout_seconds}s",
                field="sse_endpoint",
            ))
        except RuntimeError:
            # Let RuntimeError propagate to validate() for handling
            raise
        except Exception as e:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Connection failed: {str(e)}",
                field="sse_endpoint",
            ))
