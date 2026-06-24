from __future__ import annotations

from typing import Awaitable, Callable, Optional, Type, Any, Dict, Union, TYPE_CHECKING
from pydantic import BaseModel, HttpUrl
from global_utils.utils.util import validate_arguments
from global_utils.utils.async_bridge import get_async_bridge
from mas.elements.providers.mcp_server_client.mcp_server_client import McpServerClient
from mas.elements.providers.mcp_server_client.transport.enums import McpTransportType
from mas.elements.tools.common.base_tool import BaseTool
from global_utils.utils.util import json_schema_model

if TYPE_CHECKING:
    from mas.core.auth.credentials.credential import AuthCredential

AsyncHeaderProvider = Callable[..., Awaitable[Dict[str, str]]]


class McpProxyToolError(Exception):
    """Exception for MCP proxy tool errors"""
    pass


class McpProxyTool(BaseTool):
    """
    A proxy tool that forwards calls to MCP server tools by creating fresh clients per portal.
    This approach eliminates cross-event-loop thread safety issues by avoiding shared state.
    Each tool call creates a new McpServerClient in the current event loop.
    """

    def __init__(
            self,
            mcp_tool_name: str,
            mcp_url: HttpUrl,
            headers: Optional[Dict[str, str]] = None,
            transport_type: McpTransportType = McpTransportType.STREAMABLE_HTTP,
            header_provider: Optional[AsyncHeaderProvider] = None,
            auth_credential: Optional[AuthCredential] = None,
    ):
        self.name = mcp_tool_name
        self.mcp_tool_name = mcp_tool_name
        self.mcp_url = mcp_url
        self.headers = headers or {}
        self.transport_type = transport_type
        self._header_provider = header_provider
        self._auth_credential = auth_credential
        self._tool_info = None
        self._schema_initialized = False

    async def _ensure_tool_info(self, client: McpServerClient) -> None:
        """
        Fetch the tool's metadata (description + inputSchema) exactly once.
        Uses the provided fresh client from the current event loop.
        """
        if self._tool_info is not None:
            return

        tool_info = await client.get_tool_by_name(self.mcp_tool_name)

        if not tool_info:
            # If the tool isn't found, list all available tools for error context
            available = await client.get_tools()
            raise McpProxyToolError(
                f"MCP tool '{self.mcp_tool_name}' not found. Available tools: {available}"
            )

        # Cache the fetched metadata
        self._tool_info = tool_info
        self.description = tool_info.description
        self.args_schema = tool_info.inputSchema
        self._schema_initialized = True

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """
        Synchronous wrapper—only for use when no event loop is running.
        Otherwise, call `await arun(...)` directly.
        """
        try:
            with get_async_bridge() as bridge:
                return bridge.run(self.arun(*args, **kwargs))
        except Exception as e:
            raise McpProxyToolError(
                f"Synchronous execution failed for '{self.mcp_tool_name}': {e}"
            )

    async def _get_current_headers(self) -> Dict[str, str]:
        """Get headers for the current request.

        Delegates to the provider's async header_provider if available,
        otherwise falls back to static headers.
        """
        if self._header_provider:
            return await self._header_provider()
        return dict(self.headers) if self.headers else {}

    async def arun(self, *args: Any, **kwargs: Any) -> Any:
        """
        Asynchronous entry point. Steps:
          1) Resolve current auth headers (may refresh token).
          2) Create fresh MCP client in current event loop.
          3) Ensure schema is loaded (only once).
          4) Validate + prepare arguments via Pydantic model.
          5) Call tool using fresh client.
          6) On 401, attempt credential recovery and retry once.
          7) Return the extracted result.
        """
        current_headers = await self._get_current_headers()

        client = McpServerClient(
            mcp_url=self.mcp_url,
            headers=current_headers,
            transport_type=self.transport_type,
        )

        async with client:
            if not self._schema_initialized:
                await self._ensure_tool_info(client)

            mcp_args = self._prepare_arguments(kwargs)

            try:
                result = await client.call_tool(self.mcp_tool_name, mcp_args)
            except Exception as e:
                if "401" in str(e) and self._header_provider:
                    return await self._retry_after_recovery(mcp_args)
                raise McpProxyToolError(f"Failed to call '{self.mcp_tool_name}': {e}")

        return self._extract_result_content(result)

    async def _retry_after_recovery(self, mcp_args: Dict[str, Any]) -> Any:
        """Attempt credential recovery and retry the tool call once."""
        if self._auth_credential:
            recovery = await self._auth_credential.attempt_recovery()
            if not recovery.should_retry:
                raise McpProxyToolError(
                    f"Auth rejected for '{self.mcp_tool_name}': {recovery.reason}"
                )

        fresh_headers = await self._header_provider()
        async with McpServerClient(
            mcp_url=self.mcp_url,
            headers=fresh_headers,
            transport_type=self.transport_type,
        ) as client:
            result = await client.call_tool(self.mcp_tool_name, mcp_args)
        return self._extract_result_content(result)

    def _prepare_arguments(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate args against JSON schema.
        """
        if not kwargs or not self.args_schema:
            return kwargs or {}

        validate_arguments(schema=self.get_args_schema_json(), args=kwargs)
        return kwargs

    def _extract_result_content(self, result) -> Any:
        """
        Take whatever `CallToolResult` returned and pick out the most relevant piece.
        Typically MCP returns a `.content` list of TextContent or DataContent objects.
        """
        try:
            if hasattr(result, "content") and result.content:
                if isinstance(result.content, list) and len(result.content) > 0:
                    first = result.content[0]
                    if hasattr(first, "text"):
                        return first.text
                    if hasattr(first, "data"):
                        return first.data
                    return str(first)
                return str(result.content)
            return str(result)
        except Exception:
            return str(result)

    def get_args_schema_json(self) -> Dict[str, Any]:
        """
        Return the raw JSON schema that MCP provided for this tool.
        """
        return self.args_schema

    def get_args_schema_model(self) -> Optional[Type[BaseModel]]:
        """
        Dynamically build a Pydantic model from the MCP JSON schema
        so we can perform argument validation in Python.
        """
        if not self.args_schema:
            return None
        return json_schema_model(self.args_schema, self.name)

    async def refresh_schema(self) -> None:
        """
        Discard the cached schema & description, then re‐fetch them from MCP.
        """
        self._tool_info = None
        self._schema_initialized = False
        self.args_schema = None
        current_headers = await self._get_current_headers()
        client = McpServerClient(
            mcp_url=self.mcp_url,
            headers=current_headers,
            transport_type=self.transport_type,
        )
        async with client:
            await self._ensure_tool_info(client)

    async def health_check(self) -> bool:
        """
        Quickly verify that:
          1) a new connection can be established
          2) the remote tool still exists
        """
        try:
            current_headers = await self._get_current_headers()
            client = McpServerClient(
                mcp_url=self.mcp_url,
                headers=current_headers,
                transport_type=self.transport_type,
            )
            async with client:
                info = await client.get_tool_by_name(self.mcp_tool_name)
            return info is not None
        except Exception:
            return False

    def __str__(self) -> str:
        return f"McpProxyTool(name='{self.name}', mcp_tool='{self.mcp_tool_name}')"

    @classmethod
    async def create_async(
        cls,
        mcp_tool_name: str,
        mcp_url: HttpUrl,
        headers: Optional[Dict[str, str]] = None,
        transport_type: McpTransportType = McpTransportType.STREAMABLE_HTTP,
    ) -> "McpProxyTool":
        """
        Async factory method for creating a fully initialized McpProxyTool.
        
        Args:
            mcp_tool_name: Name of the MCP tool to proxy
            mcp_url: MCP server HTTP endpoint
            headers: Optional HTTP headers for authentication
            transport_type: Transport protocol to use (SSE or Streamable HTTP)
            
        Returns:
            Fully initialized McpProxyTool instance
        """
        tool = cls(
            mcp_tool_name, mcp_url,
            headers=headers, transport_type=transport_type,
        )
        
        # Initialize schema using a fresh client with headers
        client = McpServerClient(
            mcp_url=mcp_url, headers=headers,
            transport_type=transport_type,
        )
        async with client:
            await tool._ensure_tool_info(client)
        
        return tool

    @classmethod
    def create_sync(
        cls,
        mcp_tool_name: str,
        mcp_url: HttpUrl,
        headers: Optional[Dict[str, str]] = None,
        transport_type: McpTransportType = McpTransportType.STREAMABLE_HTTP,
    ) -> "McpProxyTool":
        """
        Sync factory method for creating a fully initialized McpProxyTool.
        Uses AsyncBridge internally to handle the async initialization.
        
        Args:
            mcp_tool_name: Name of the MCP tool to proxy
            mcp_url: MCP server HTTP endpoint
            headers: Optional HTTP headers for authentication
            transport_type: Transport protocol to use (SSE or Streamable HTTP)
            
        Returns:
            Fully initialized McpProxyTool instance
        """
        with get_async_bridge() as bridge:
            return bridge.run(cls.create_async(
                mcp_tool_name, mcp_url,
                headers, transport_type=transport_type,
            ))

    @classmethod
    def create_with_cached_schema(
        cls,
        mcp_tool_name: str,
        mcp_url: HttpUrl,
        tool_info,
        headers: Optional[Dict[str, str]] = None,
        transport_type: McpTransportType = McpTransportType.STREAMABLE_HTTP,
        header_provider: Optional[AsyncHeaderProvider] = None,
        auth_credential: Optional[AuthCredential] = None,
    ) -> McpProxyTool:
        """
        Create tool with pre-cached schema (no connection needed).
        This is the optimization — tool creation without connection.
        """
        tool = cls(
            mcp_tool_name, mcp_url,
            headers=headers, transport_type=transport_type,
            header_provider=header_provider,
            auth_credential=auth_credential,
        )

        tool._tool_info = tool_info
        tool.description = tool_info.description or ""
        tool.args_schema = tool_info.inputSchema or {}
        tool._schema_initialized = True

        return tool

    def get_sandbox_config(self) -> Dict[str, Any]:
        """Extract serializable config for sandbox execution.

        Resolves auth headers in the worker (where auth closures are
        available) and returns a plain dict of strings that can cross
        the cloudpickle boundary.
        """
        with get_async_bridge() as bridge:
            headers = bridge.run(self._get_current_headers())
        return {
            "_tool_type": "mcp_proxy",
            "mcp_url": str(self.mcp_url),
            "mcp_tool_name": self.mcp_tool_name,
            "headers": headers,
            "transport_type": self.transport_type.value,
        }

    def __repr__(self) -> str:
        desc = (self.description[:50] + "...") if self.description else "No description"
        return (
            f"McpProxyTool(name='{self.name}', mcp_tool_name='{self.mcp_tool_name}', "
            f"transport={self.transport_type.value}, "
            f"description='{desc}', endpoint='{self.mcp_url}')"
        )
