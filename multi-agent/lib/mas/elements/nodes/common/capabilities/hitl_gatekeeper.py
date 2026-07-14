"""Shared tool-call gating logic for HITL approval.

Encapsulates the resolve → check → request flow that is identical
across all agent types.  SDK-specific adapters (``HITLExecutionHandler``,
``HITLMiddleware``, ``HITLHook``) call :meth:`check` and translate the
result into their SDK's response format.

By centralising this logic we satisfy SRP (each adapter only handles
SDK translation) and DRY (the gating flow lives in one place).
"""
import logging
from typing import Dict, Optional

from mas.core.hitl.models import (
    ApprovalRequest,
    ApprovalResponse,
    ApprovalType,
    RequestOrigin,
    ToolAccessMode,
    ToolApprovalPolicy,
)
from mas.core.hitl.ports import ApprovalGate
from mas.elements.tools.common.base_tool import BaseTool

logger = logging.getLogger(__name__)


class HITLToolGatekeeper:
    """Resolves tool access modes, checks the approval policy, and
    requests human approval via the ``ApprovalGate``.

    Construction:
        gate               – the channel-backed approval gate
        policy             – decides which access modes require approval
        tool_registry      – domain ``BaseTool`` instances (explicit access_mode)
        origin             – identifies the requesting node / session
        builtin_access_modes – SDK-specific built-in tool → ToolAccessMode map
        default_access_mode  – fallback for unknown tools (WRITE = secure default)
    """

    def __init__(
        self,
        *,
        gate: ApprovalGate,
        policy: ToolApprovalPolicy,
        tool_registry: Dict[str, BaseTool],
        origin: RequestOrigin,
        builtin_access_modes: Optional[Dict[str, ToolAccessMode]] = None,
        default_access_mode: ToolAccessMode = ToolAccessMode.WRITE,
    ) -> None:
        self._gate = gate
        self._policy = policy
        self._tool_registry = tool_registry
        self._origin = origin
        self._builtin_modes = builtin_access_modes or {}
        self._default_mode = default_access_mode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_access_mode(self, tool_name: str) -> ToolAccessMode:
        """Determine the access mode for *tool_name*.

        Resolution order:
        1. Domain tool registry (our ``BaseTool`` instances)
        2. SDK built-in tool mapping (passed at construction)
        3. Configurable default (WRITE — secure by default)
        """
        domain_tool = self._tool_registry.get(tool_name)
        if domain_tool is not None:
            return domain_tool.access_mode
        return self._builtin_modes.get(tool_name, self._default_mode)

    def check(
        self,
        tool_name: str,
        tool_args: dict,
        *,
        reasoning: Optional[str] = None,
    ) -> Optional[ApprovalResponse]:
        """Gate a single tool call through the HITL approval system.

        Returns ``None`` when the tool is auto-approved (READ mode or
        policy says no approval needed).  Otherwise blocks until the
        human responds and returns the ``ApprovalResponse``.
        """
        access_mode = self.resolve_access_mode(tool_name)

        if not self._policy.requires_approval(tool_name, access_mode):
            logger.debug(
                "HITL gatekeeper auto-approved '%s' (mode=%s)",
                tool_name, access_mode.value,
            )
            return None

        logger.info(
            "HITL gatekeeper requesting approval: tool=%s, mode=%s, node=%s",
            tool_name, access_mode.value, self._origin.node_uid,
        )

        domain_tool = self._tool_registry.get(tool_name)
        request = ApprovalRequest(
            request_id=ApprovalRequest.generate_id(),
            type=ApprovalType.TOOL_EXECUTION,
            origin=self._origin,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_description=domain_tool.description if domain_tool else "",
            tool_access_mode=access_mode,
            reasoning=reasoning,
        )
        response = self._gate.request_approval(request)

        logger.info(
            "HITL gatekeeper decision: tool=%s, decision=%s",
            tool_name, response.decision.value,
        )
        return response
