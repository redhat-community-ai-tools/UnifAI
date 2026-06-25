"""
HITL capability mixin for agent nodes.

Provides the shared state and logic for Human-in-the-Loop gating:
  - ``set_approval_gate`` / ``set_approval_policy`` (SupportsHITL protocol)
  - ``_should_activate_hitl()``  — decides whether HITL is active
  - ``hitl_session_id``          — session ID from the execution context

Mixed into any node that runs tools and may need human approval
(CustomAgentNode, DeepAgentNode, ClaudeAgentNode, …).
Nodes that don't use tools (BranchChooser, FinalAnswer, etc.)
never mix this in — Interface Segregation.
"""
import logging
from typing import Any, Optional

from mas.core.execution_context import ExecutionContextHolder
from mas.core.hitl.models import HITLMode, ToolApprovalPolicy
from mas.core.hitl.ports import ApprovalGate

logger = logging.getLogger(__name__)


class HITLCapableMixin:
    """Mixin for nodes that support HITL tool-call gating.

    Carries:
      - ``_hitl_mode``          (from config: ASK / SKIP / DYNAMIC)
      - ``_execution_holder``   (runtime reference to ExecutionContext)
      - ``_approval_gate``      (injected at runtime by NodeRuntimeBinder)
      - ``_approval_policy``    (injected at runtime by NodeRuntimeBinder)

    The binder injects gate/policy via the ``SupportsHITL`` protocol
    which checks for ``set_approval_gate`` and ``set_approval_policy``.
    """

    def __init__(
        self,
        *,
        hitl_mode: HITLMode = HITLMode.SKIP,
        execution_holder: Optional[ExecutionContextHolder] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._hitl_mode = HITLMode(hitl_mode) if isinstance(hitl_mode, str) else hitl_mode
        self._execution_holder = execution_holder
        self._approval_gate: Optional[ApprovalGate] = None
        self._approval_policy: Optional[ToolApprovalPolicy] = None

    # ── SupportsHITL protocol ─────────────────────────────────

    def set_approval_gate(self, gate: Optional[ApprovalGate]) -> None:
        self._approval_gate = gate

    def set_approval_policy(self, policy: Optional[ToolApprovalPolicy]) -> None:
        self._approval_policy = policy

    # ── Shared decision logic ─────────────────────────────────

    def _should_activate_hitl(self) -> bool:
        """Decide whether HITL gating is active for this execution run.

        Combines the static ``hitl_mode`` from config with the runtime
        gate/policy injection and (for DYNAMIC) the ExecutionContext flag.
        """
        gate_present = (self._approval_gate is not None
                        and self._approval_policy is not None)
        if not gate_present:
            return False

        if self._hitl_mode == HITLMode.ASK:
            return True
        if self._hitl_mode == HITLMode.SKIP:
            return False
        if self._execution_holder is not None:
            try:
                return self._execution_holder.context.hitl_enabled
            except RuntimeError:
                return False
        return False

    @property
    def hitl_session_id(self) -> str:
        """Session ID from the execution context (filled at runtime)."""
        if self._execution_holder is None:
            return ""
        try:
            return self._execution_holder.context.session_id
        except (RuntimeError, AttributeError):
            return ""
