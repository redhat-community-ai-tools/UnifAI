"""
Orchestrator-specific phase provider — thin coordinator.

Wires together:
  PhaseRegistry  (owns all Phase objects)
  PhaseMachine   (cascade + iteration limits)
  ContextFormatter (plan/workspace → ChatMessages)

Owns:
  Snapshot caching, status contextualization, cycle lifecycle.

~200 lines (down from 706).
"""

import logging
from typing import List, Callable, Any, Optional

from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.llms.common.chat.message import ChatMessage
from mas.elements.nodes.common.agent.phases.unified_phase_provider import PhaseProvider
from mas.elements.nodes.common.agent.phases.phase_protocols import PhaseState, create_phase_state
from mas.elements.nodes.common.agent.phases.models import PhaseValidationContext

from .phases.constants import OrchestratorPhase  # re-exported for backward compat
from .phases.base import PhaseDependencies, PromptContext
from .phases.planning import PlanningPhase
from .phases.execution import ExecutionPhase
from .phases.monitoring import MonitoringPhase
from .phases.synthesis import SynthesisPhase
from .phases.registry import OrchestratorPhaseRegistry
from .phases.phase_machine import PhaseMachine
from .phases.context_formatter import ContextFormatter
from .phases.models import PhaseIterationLimits
from .context.snapshot import IterationSnapshot
from .context import OrchestratorContextBuilder
from .workplan_logger import WorkPlanLogger

logger = logging.getLogger(__name__)


class OrchestratorPhaseProvider(PhaseProvider):
    """
    Thin coordinator for orchestrator phases.

    Delegates per-phase knowledge to Phase classes, transitions to
    PhaseMachine, context formatting to ContextFormatter, and debug
    logging to WorkPlanLogger.  Keeps only lifecycle and status
    contextualization logic.
    """

    def __init__(
        self,
        domain_tools: List[BaseTool],
        get_adjacent_nodes: Callable[[], Any],
        send_task: Callable[..., Any],
        node_uid: str,
        thread_id: str,
        get_workload_service: Callable[[], Any],
        context_builder: Optional[OrchestratorContextBuilder] = None,
        iteration_limits: Optional[PhaseIterationLimits] = None,
    ):
        self._node_uid = node_uid
        self._thread_id = thread_id
        self._get_workload_service = get_workload_service
        self._get_adjacent_nodes = get_adjacent_nodes
        self._context_builder = context_builder

        # Orchestrator context (set before each cycle)
        self._current_orch_context = None
        self._current_user_request: Optional[str] = None
        self._phase_changed: bool = True
        self._cached_snapshot: Optional[IterationSnapshot] = None
        self._plan_updated_at_cycle_start: Optional[str] = None

        # Build shared dependency container
        adjacent_nodes = get_adjacent_nodes()
        deps = PhaseDependencies(
            get_thread_id=lambda: self._thread_id,
            get_owner_uid=lambda: self._node_uid,
            get_workload_service=get_workload_service,
            send_task=send_task,
            get_current_thread=lambda: self._get_current_thread(),
            get_thread_service=lambda: get_workload_service().get_thread_service(),
            get_workspace_service=lambda: get_workload_service().get_workspace_service(),
            check_adjacency=lambda uid: uid in adjacent_nodes,
            get_adjacent_nodes=get_adjacent_nodes,
            domain_tools=list(domain_tools),
        )

        # Registry initialises all Phase objects with deps
        self._registry = OrchestratorPhaseRegistry(
            phases=[PlanningPhase(), ExecutionPhase(), MonitoringPhase(), SynthesisPhase()],
            deps=deps,
        )

        # Sub-components
        self._machine = PhaseMachine(
            registry=self._registry,
            limits=iteration_limits or PhaseIterationLimits(),
        )
        self._formatter = ContextFormatter(
            thread_id=self._thread_id,
            node_uid=self._node_uid,
            get_adjacent_nodes=get_adjacent_nodes,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_current_thread(self):
        return self._get_workload_service().get_thread(self._thread_id)

    # ------------------------------------------------------------------
    # Lifecycle — called by orchestrator_node before each cycle
    # ------------------------------------------------------------------

    def set_orch_context(self, orch_context) -> None:
        """
        Set orchestration context and snapshot the plan timestamp so
        _contextualize_status can detect mid-cycle modifications.
        """
        self._current_orch_context = orch_context
        try:
            ws = self._get_workload_service().get_workspace_service()
            plan = ws.load_work_plan(self._thread_id, self._node_uid)
            self._plan_updated_at_cycle_start = plan.updated_at if plan else None
        except Exception:
            self._plan_updated_at_cycle_start = None

    def set_current_user_request(self, request: str) -> None:
        self._current_user_request = request

    # ------------------------------------------------------------------
    # PhaseProvider interface — REQUIRED
    # ------------------------------------------------------------------

    def get_supported_phases(self) -> List[str]:
        return self._registry.names()

    def get_tools_for_phase(self, phase_name: str) -> List[BaseTool]:
        p = self._registry.get(phase_name)
        return p.tools if p else []

    def update_phase(self, current_phase: str) -> str:
        status = self._contextualize_status(self._snapshot.status)
        final = self._machine.update_phase(current_phase, status)
        if final != current_phase:
            if self._context_builder:
                self._context_builder.record_phase_transition(
                    from_phase=current_phase, to_phase=final, reason="cascade",
                )
            try:
                ws = self._get_workload_service().get_workspace_service()
                WorkPlanLogger.log_after_transition(ws, self._thread_id, self._node_uid, final)
            except Exception:
                pass
        return final

    def can_finish_now(self, current_phase: str) -> bool:
        try:
            ctx = self.get_phase_context()
            if not ctx or not ctx.work_plan_status:
                return True

            status = ctx.work_plan_status

            if current_phase == OrchestratorPhase.SYNTHESIS:
                return True

            if status.has_remote_waiting:
                if (not status.has_responses
                        and not status.has_local_ready
                        and not status.has_remote_ready):
                    return True

            return False
        except Exception:
            return True

    def get_phase_context(self) -> PhaseState:
        try:
            raw_status = self._snapshot.status
            status = self._contextualize_status(raw_status)
            return create_phase_state(
                work_plan_status=status,
                thread_id=self._thread_id,
                node_uid=self._node_uid,
            )
        except Exception:
            return create_phase_state(
                thread_id=self._thread_id,
                node_uid=self._node_uid,
            )

    # ------------------------------------------------------------------
    # PhaseProvider interface — OPTIONAL overrides
    # ------------------------------------------------------------------

    def get_initial_phase(self) -> str:
        return self._registry.initial().name

    def get_terminal_phase(self) -> str:
        return self._registry.terminal().name

    def is_terminal_phase(self, phase_name: str) -> bool:
        p = self._registry.get(phase_name)
        return p.is_terminal if p else False

    def begin_iteration(self) -> None:
        self._cached_snapshot = IterationSnapshot.capture(
            get_workload_service=self._get_workload_service,
            get_adjacent_nodes=self._get_adjacent_nodes,
            thread_id=self._thread_id,
            node_uid=self._node_uid,
        )

    def end_iteration(self) -> None:
        self._cached_snapshot = None

    def set_phase_changed(self, changed: bool) -> None:
        self._phase_changed = changed

    def get_dynamic_context_messages(self, phase_name: str) -> List[ChatMessage]:
        p = self._registry.get(phase_name)
        if not p:
            return []
        snap = self._snapshot
        ws = snap.workspace_service or self._get_workload_service().get_workspace_service()
        return self._formatter.build_dynamic_context_messages(
            phase=p,
            plan=snap.plan,
            workspace_service=ws,
            orch_context=self._current_orch_context,
            phase_changed=self._phase_changed,
        )

    def get_phase_static_context(self, phase_name: str) -> List[ChatMessage]:
        p = self._registry.get(phase_name)
        if not p:
            return []
        return self._formatter.build_static_context(phase=p)

    def build_focused_prompt(self, phase: str, phase_changed: bool) -> str:
        p = self._registry.get(phase)
        if not p:
            return ""
        snap = self._snapshot
        ctx = PromptContext(
            trigger_reason=(
                self._current_orch_context.trigger.reason
                if self._current_orch_context else None
            ),
            changed_items=(
                self._current_orch_context.trigger.changed_items
                if self._current_orch_context else []
            ),
            plan=snap.plan,
            status=snap.status,
            phase_changed=phase_changed,
            user_request=self._current_user_request or "",
        )
        return p.build_focused_prompt(ctx)

    def build_phase_prompt(self, phase_name: str) -> str:
        p = self._registry.get(phase_name)
        if not p:
            return ""
        guidance = p.get_guidance()
        validation = p.run_validation(self._build_validation_context())
        if validation:
            return f"{guidance}\n\n{validation}"
        return guidance

    def get_phase_guidance(self, phase_name: str) -> str:
        p = self._registry.get(phase_name)
        return p.get_guidance() if p else ""

    def get_phase_validation(self, phase_name: str) -> str:
        p = self._registry.get(phase_name)
        if not p:
            return ""
        return p.run_validation(self._build_validation_context())

    # ------------------------------------------------------------------
    # Status contextualization
    # ------------------------------------------------------------------

    def _contextualize_status(self, raw_status):
        """
        Override stale plan status for NEW_REQUEST triggers.

        The phase machine routes purely on WorkPlanStatus. This method
        ensures is_complete reflects the CURRENT situation, not a
        leftover from a previous cycle.
        """
        if raw_status is None:
            return raw_status

        from .context.models import CycleTriggerReason

        if not self._current_orch_context:
            return raw_status

        reason = self._current_orch_context.trigger.reason

        if reason == CycleTriggerReason.NEW_REQUEST and raw_status.is_complete:
            if not self._is_plan_modified_this_cycle():
                return raw_status.model_copy(update={"is_complete": False})

        return raw_status

    def _is_plan_modified_this_cycle(self) -> bool:
        if self._plan_updated_at_cycle_start is None:
            return False
        plan = self._snapshot.plan
        if not plan:
            return False
        return plan.updated_at != self._plan_updated_at_cycle_start

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    @property
    def _snapshot(self) -> IterationSnapshot:
        if self._cached_snapshot is None:
            self.begin_iteration()
        return self._cached_snapshot

    # ------------------------------------------------------------------
    # Validation context
    # ------------------------------------------------------------------

    def _build_validation_context(self) -> PhaseValidationContext:
        phase_state = self.get_phase_context()
        snap = self._snapshot
        return PhaseValidationContext(
            phase_state=phase_state,
            thread_id=self._thread_id,
            node_uid=self._node_uid,
            plan=snap.plan,
            adjacent_nodes=snap.adjacent_nodes,
        )
