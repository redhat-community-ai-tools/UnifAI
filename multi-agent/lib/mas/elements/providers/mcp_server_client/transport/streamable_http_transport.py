"""
Streamable HTTP transport manager for MCP connections.

Uses ``mcp.client.streamable_http.streamable_http_client`` to open a
bidirectional HTTP transport to the MCP server. Supports custom HTTP
headers for authentication.
"""

from contextlib import asynccontextmanager
from typing import Any, Tuple

from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

from .base_transport import BaseTransportManager
from .enums import McpTransportType


class StreamableHttpTransportManager(BaseTransportManager):
    """
    MCP transport over Streamable HTTP.

    Supports custom HTTP headers (e.g. Bearer token authentication)
    passed through to the underlying HTTP client.
    """

    @property
    def transport_type(self) -> McpTransportType:
        return McpTransportType.STREAMABLE_HTTP

    @property
    def _transport_label(self) -> str:
        return "Streamable HTTP"

    @asynccontextmanager
    async def _create_transport_context(self) -> Any:
        # The SDK does not close caller-provided HTTP clients. Keep the client
        # alive until the transport exits, including when connection fails.
        async with create_mcp_http_client(headers=self.headers) as http_client:
            async with streamable_http_client(
                url=self.endpoint, http_client=http_client,
            ) as (read_stream, write_stream, _):
                yield read_stream, write_stream

    async def _enter_transport_context(self, ctx: Any) -> Tuple:
        read_stream, write_stream = await ctx.__aenter__()
        return read_stream, write_stream
