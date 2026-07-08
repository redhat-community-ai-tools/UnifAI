"""HITL execution handler — gates WRITE/DESTRUCTIVE tool calls through
an ApprovalGate while executing READ tools automatically.

Sits alongside AutoExecutionHandler and GuidedExecutionHandler as a
pluggable ExecutionHandler strategy.  The AgentIterator is unaware of
which handler it uses (Liskov substitution).

Delegates the resolve → check → request flow to ``HITLToolGatekeeper``
(shared with ``HITLMiddleware`` and ``HITLHook``).  This handler is
responsible only for translating gatekeeper results into
``AgentStep`` / ``AgentObservation`` objects consumed by the iterator.
"""
import logging
from typing import Dict, Iterator, List

from mas.core.hitl.models import ApprovalDecision, RequestOrigin, ToolApprovalPolicy
from mas.core.hitl.ports import ApprovalGate
from mas.elements.nodes.common.capabilities.hitl_gatekeeper import HITLToolGatekeeper
from mas.elements.tools.common.base_tool import BaseTool

from ..primitives import (
    AgentAction,
    AgentObservation,
    AgentStep,
    StepType,
)
from .executor import AgentActionExecutor
from .handlers import ExecutionHandler

logger = logging.getLogger(__name__)


class HITLExecutionHandler(ExecutionHandler):
    """Execution handler that gates tool calls through human approval.

    READ tools execute immediately.  WRITE / DESTRUCTIVE tools are
    sent to the ``ApprovalGate`` and the handler blocks until the
    human responds (or the gate times out).

    Four possible human decisions:
      APPROVE  → execute the action as-is
      MODIFY   → execute with human-modified arguments
      REJECT   → skip execution, feed rejection reason to agent
      REDIRECT → skip execution, feed human instruction to agent
    """

    def __init__(
        self,
        action_executor: AgentActionExecutor,
        *,
        gate: ApprovalGate,
        policy: ToolApprovalPolicy,
        tool_registry: Dict[str, BaseTool],
        node_uid: str,
        node_display_name: str,
        session_id: str,
    ) -> None:
        super().__init__(action_executor)
        self._gatekeeper = HITLToolGatekeeper(
            gate=gate,
            policy=policy,
            tool_registry=tool_registry,
            origin=RequestOrigin(
                node_uid=node_uid,
                node_display_name=node_display_name,
                session_id=session_id,
            ),
        )

    # ------------------------------------------------------------------
    # ExecutionHandler contract
    # ------------------------------------------------------------------

    def handle_actions(self, actions: List[AgentAction]) -> Iterator[AgentStep]:
        if not actions:
            return

        for action in actions:
            response = self._gatekeeper.check(
                action.tool, action.tool_input, reasoning=action.reasoning,
            )

            if response is None:
                yield from self._execute_and_yield(action)
                continue

            match response.decision:
                case ApprovalDecision.APPROVE:
                    yield from self._execute_and_yield(action)

                case ApprovalDecision.MODIFY:
                    modified = self._apply_modification(action, response.modified_args)
                    yield from self._execute_and_yield(modified, modified=True)

                case ApprovalDecision.REJECT:
                    yield self._rejection_step(
                        action,
                        f"Action rejected by human operator. "
                        f"Reason: {response.feedback}. "
                        f"Please choose a safer approach.",
                    )

                case ApprovalDecision.REDIRECT:
                    yield self._rejection_step(
                        action,
                        f"Human operator instruction: {response.feedback}",
                    )

    def is_ready_for_next_iteration(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _execute_and_yield(
        self,
        action: AgentAction,
        *,
        modified: bool = False,
    ) -> Iterator[AgentStep]:
        obs = self.action_executor.execute(action)
        self.observations.append(obs)
        yield AgentStep(
            StepType.OBSERVATION,
            obs,
            metadata={
                "action_id": obs.action_id,
                "execution_time": obs.execution_time,
                "success": obs.success,
                "handler": "hitl",
                "modified": modified,
            },
        )

    @staticmethod
    def _apply_modification(
        action: AgentAction,
        modified_args: dict,
    ) -> AgentAction:
        if not modified_args:
            return action
        from dataclasses import replace
        return replace(action, tool_input=modified_args)

    def _rejection_step(self, action: AgentAction, message: str) -> AgentStep:
        obs = AgentObservation(
            action_id=action.id,
            tool=action.tool,
            output=message,
            success=False,
            error=None,
            execution_time=0.0,
        )
        self.observations.append(obs)
        return AgentStep(
            StepType.OBSERVATION,
            obs,
            metadata={
                "action_id": action.id,
                "handler": "hitl",
                "rejected": True,
            },
        )
