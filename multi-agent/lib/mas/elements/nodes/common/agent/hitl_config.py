"""Typed configuration for the HITL execution handler.

Replaces the previous untyped ``Dict[str, Any]`` (``hitl_kwargs``)
that was forwarded via ``AgentConfig`` → ``ExecutionHandlerFactory``.

Lives in its own module to avoid a circular import between
``config.py`` (which imports ``ExecutionMode`` from ``handlers.py``)
and ``handlers.py`` (which needs ``HITLHandlerConfig``).
"""

from dataclasses import dataclass
from typing import Dict

from mas.core.hitl.models import ToolApprovalPolicy
from mas.core.hitl.ports import ApprovalGate
from mas.elements.tools.common.base_tool import BaseTool


@dataclass(frozen=True)
class HITLHandlerConfig:
    """All dependencies required by ``HITLExecutionHandler``.

    Frozen so it can be treated as a value object once constructed.
    """

    gate: ApprovalGate
    policy: ToolApprovalPolicy
    tool_registry: Dict[str, BaseTool]
    node_uid: str
    node_display_name: str
    session_id: str
