"""Tiny MCP server (SSE) with two harmless tools. For tests only."""
from datetime import datetime, timezone
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="unifai-demo-mcp", host="0.0.0.0", port=8004)


@mcp.tool()
def utc_now() -> str:
    """Current UTC time (ISO-8601)."""
    return datetime.now(timezone.utc).isoformat()


@mcp.tool()
def echo(text: str) -> str:
    """Echo the text back."""
    return text


if __name__ == "__main__":
    mcp.run(transport="sse")
