"""
Streamable HTTP transport manager for MCP connections.

Uses ``mcp.client.streamable_http.streamable_http_client`` to open a
bidirectional HTTP transport to the MCP server. Supports custom HTTP
headers for authentication.
"""

from typing import Any, Tuple

from mcp.client.streamable_http import streamable_http_client

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

    def _create_transport_context(self) -> Any:
        return streamable_http_client(
            url=self.endpoint,
            headers=self.headers,
        )

    async def _enter_transport_context(self, ctx: Any) -> Tuple:
        read_stream, write_stream, _ = await ctx.__aenter__()
        return read_stream, write_stream
