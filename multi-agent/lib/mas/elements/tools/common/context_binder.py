"""Late-bind execution context into tools that support it.

Agent nodes call ``bind_tool_context`` at execution time to inject
``session_id`` and ``agent_id`` into tools that need deterministic
naming — e.g. ``SandboxExecTool`` for sandbox lifecycle on a shared
gateway.
"""

import logging
from typing import List

from mas.elements.tools.common.base_tool import BaseTool

logger = logging.getLogger(__name__)


def bind_tool_context(
    tools: List[BaseTool],
    *,
    session_id: str = "",
    agent_id: str = "",
) -> None:
    """Inject runtime context into tools that expose ``bind_context()``.

    Failures are logged but never propagated — a broken tool must not
    crash the agent's compilation or startup.
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
