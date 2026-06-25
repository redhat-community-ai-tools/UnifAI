"""Late-bind execution context into tools and release resources on close.

Agent nodes call ``bind_tool_context`` to inject ``session_id`` and
``agent_id`` into tools that need deterministic naming.

Agent nodes call ``get_sandbox_wrapped_mcp_tools`` inside their
existing collection methods to decide whether MCP tools should be
wrapped for sandbox routing (either wrapped or originals, never both).

Agent nodes call ``close_tools`` in a ``finally`` block to release
resources (gRPC channels, sandbox containers).
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
    """Inject runtime context into tools that expose ``bind_context()``.

    Uses duck typing — any tool with a ``bind_context`` method is called.
    Failures are logged but never propagated so a broken tool does not
    crash the agent's startup.
    """
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


def find_sandbox_tool(tools: List[BaseTool]) -> Optional[Any]:
    """Return the first ``SandboxExecTool`` in *tools*, or ``None``.

    Handles the case where the ``openshell`` package is not installed
    (the tool class cannot be imported) by returning ``None`` — the
    caller falls through to its non-sandbox code path.  This is safe
    because the tool factory would have already failed at element
    creation time if the package were missing while a sandbox tool was
    actually configured.
    """
    try:
        from mas.elements.tools.sandbox_exec.sandbox_exec import SandboxExecTool
    except ImportError:
        return None
    return next((t for t in tools if isinstance(t, SandboxExecTool)), None)


def get_sandbox_wrapped_mcp_tools(
    domain_tools: List[BaseTool],
    mcp_providers: List[Any],
) -> Optional[List[BaseTool]]:
    """Return sandbox-wrapped MCP tools if routing is active, else ``None``.

    Called by each agent node's existing tool collection method
    (``_collect_tools``, ``_get_all_tools``, ``_collect_langchain_tools``)
    to decide: use wrapped tools (sandbox) or originals (worker).

    When this returns ``None``, the caller should iterate
    ``mcp_providers`` and collect originals as it does today.

    Args:
        domain_tools: The node's domain tools list (checked for the
            presence of a ``SandboxExecTool`` instance).
        mcp_providers: MCP providers whose tools will be wrapped.

    Returns:
        A list of ``SandboxToolProxy`` instances, or ``None`` if sandbox
        routing is not active.
    """
    sandbox_tool = find_sandbox_tool(domain_tools)
    if sandbox_tool is None:
        return None

    try:
        from mas.elements.tools.common.sandbox_tool_proxy import SandboxToolProxy
    except ImportError:
        logger.error(
            "SandboxExecTool is configured but 'openshell' package is not "
            "installed. Install with: pip install 'mas[openshell]'"
        )
        raise

    mcp_urls: List[str] = []
    wrapped: List[BaseTool] = []
    for provider in mcp_providers:
        if hasattr(provider, "mcp_url"):
            mcp_urls.append(str(provider.mcp_url))
        for tool in provider.get_tools():
            wrapped.append(SandboxToolProxy(tool, sandbox_tool))

    if mcp_urls and hasattr(sandbox_tool, "add_allowed_endpoints"):
        sandbox_tool.add_allowed_endpoints(mcp_urls)
        logger.info(
            "Registered %d MCP endpoint(s) for sandbox network policy: %s",
            len(mcp_urls),
            mcp_urls,
        )

    logger.info(
        "Sandbox routing enabled: wrapped %d MCP tools via %s",
        len(wrapped),
        sandbox_tool.name,
    )
    return wrapped


def close_tools(tools: List[BaseTool]) -> None:
    """Release resources held by tools that expose ``close()``.

    Called at the end of node execution in a ``finally`` block.
    Failures are logged but never propagated so cleanup errors
    do not mask the agent's actual execution result.
    """
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
