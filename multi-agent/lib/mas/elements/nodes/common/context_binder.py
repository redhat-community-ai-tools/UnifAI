"""Late-bind execution context into tools and release resources on close.

Agent nodes call ``bind_tool_context`` to inject ``session_id`` and
``agent_id`` into tools that need deterministic naming.

Agent nodes call ``get_sandbox_wrapped_mcp_tools`` to wrap MCP tools
for sandbox routing when a sandbox is attached.

Agent nodes call ``close_tools`` in a ``finally`` block to release
resources (gRPC channels, etc.).
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from mas.elements.tools.common.base_tool import BaseTool

logger = logging.getLogger(__name__)


def bind_tool_context(
    tools: List[BaseTool],
    *,
    session_id: str = "",
    agent_id: str = "",
) -> None:
    """Inject runtime context into tools that expose ``bind_context()``."""
    for tool in tools:
        if hasattr(tool, "bind_context"):
            try:
                tool.bind_context(session_id=session_id, agent_id=agent_id)
            except Exception:
                logger.warning(
                    "Failed to bind context to tool %s",
                    getattr(tool, "name", "unknown"),
                    exc_info=True,
                )


def get_sandbox_wrapped_mcp_tools(
    sandbox: Optional[Any],
    mcp_providers: List[Any],
) -> Optional[List[BaseTool]]:
    """Return sandbox-wrapped MCP tools if a sandbox is attached, else None.

    When this returns None, the caller should iterate mcp_providers
    and collect originals as it does today.
    """
    if sandbox is None:
        return None

    try:
        from mas.elements.sandboxes.common.sandbox_tool_proxy import SandboxToolProxy
    except ImportError:
        logger.error(
            "Sandbox is configured but 'openshell' package is not "
            "installed. Install with: pip install 'mas[openshell]'"
        )
        raise

    mcp_urls: List[str] = []
    wrapped: List[BaseTool] = []
    for provider in mcp_providers:
        if hasattr(provider, "mcp_url"):
            mcp_urls.append(str(provider.mcp_url))
        for tool in provider.get_tools():
            wrapped.append(SandboxToolProxy(tool, sandbox))

    if mcp_urls and hasattr(sandbox, "add_allowed_endpoints"):
        sandbox.add_allowed_endpoints(mcp_urls)
        logger.info(
            "Registered %d MCP endpoint(s) for sandbox network policy: %s",
            len(mcp_urls),
            mcp_urls,
        )

    logger.info(
        "Sandbox routing enabled: wrapped %d MCP tools",
        len(wrapped),
    )
    return wrapped


def close_tools(tools: List[BaseTool]) -> None:
    """Release resources held by tools that expose ``close()``."""
    for tool in tools:
        if hasattr(tool, "close") and callable(getattr(tool, "close")):
            try:
                tool.close()
            except Exception:
                logger.warning(
                    "Failed to close tool %s",
                    getattr(tool, "name", "unknown"),
                    exc_info=True,
                )
