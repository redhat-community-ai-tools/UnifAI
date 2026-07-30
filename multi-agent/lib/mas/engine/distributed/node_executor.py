"""
Stateless node execution logic for distributed engines.

Rebuilds a single node (or condition) from its mini-blueprint,
injects the real StepContext, runs it, and discards it.
Like a Flask handler — any worker can execute any node.

Runtime capabilities (streaming channel, HITL gate/policy) are
injected via ``NodeRuntimeBinder`` using capability protocols —
no ``hasattr`` duck-typing.

Tracing is owned here so that every distributed engine (Temporal,
Celery, …) gets session-level traces for free — adapters stay thin.
"""
from typing import Any, Dict, Optional

from mas.blueprints.models.blueprint import BlueprintSpec
from mas.core.contracts import SupportsStepContext
from mas.core.enums import ResourceCategory
from mas.core.execution_context import ExecutionContext, ExecutionContextHolder
from mas.core.runtime_binder import NodeRuntimeBinder, NodeRuntimeBindings
from mas.core.tracing import TracingService
from mas.graph.models.step_context import StepContext
from mas.graph.state.graph_state import GraphState
from mas.session.building.workflow_session_factory import WorkflowSessionFactory


class NodeExecutor:
    """
    Stateless executor for individual graph nodes and conditions.

    Created once at worker startup with a shared session factory
    and a ``NodeRuntimeBinder``.  Each call builds a fresh node from
    the mini-blueprint, injects context, runs it, and returns the result.

    Channel/HITL creation is NOT this class's concern — callers
    provide a ``NodeRuntimeBindings`` value object.
    """

    def __init__(
        self,
        session_factory: WorkflowSessionFactory,
        binder: Optional[NodeRuntimeBinder] = None,
        tracing_service: TracingService = None,
    ) -> None:
        self._factory = session_factory
        self._binder = binder or NodeRuntimeBinder.default()
        self._tracing = tracing_service

    def execute_node(
        self,
        node_uid: str,
        node_blueprint: Dict[str, Any],
        step_context: Optional[StepContext],
        state: GraphState,
        bindings: Optional[NodeRuntimeBindings] = None,
        execution_context: Optional[ExecutionContext] = None,
    ) -> GraphState:
        """
        Build ONE node from its mini-blueprint, inject context, run it.

        Wraps execution in a session-level trace (deterministic trace_id
        from session_id) so that all nodes in the same session appear
        under one Langfuse trace.

        Runtime capabilities (channel, HITL) are applied from the
        ``bindings`` value object via the binder's protocol checks.
        """
        session_id = ""
        user_id = ""
        if execution_context:
            session_id = execution_context.session_id or ""
            user_id = getattr(execution_context, "identity_id", "") or ""

        with self._tracing.trace_session(
            session_id=session_id,
            user_id=user_id,
            metadata={"node_uid": node_uid},
        ):
            try:
                return self._execute_node_inner(
                    node_uid, node_blueprint, step_context,
                    state, bindings, execution_context,
                )
            finally:
                self._tracing.flush()

    def _execute_node_inner(
        self,
        node_uid: str,
        node_blueprint: Dict[str, Any],
        step_context: Optional[StepContext],
        state: GraphState,
        bindings: Optional[NodeRuntimeBindings] = None,
        execution_context: Optional[ExecutionContext] = None,
    ) -> GraphState:
        mini_bp = BlueprintSpec.model_validate(node_blueprint)

        ctx_holder = ExecutionContextHolder()
        rt_plan = self._factory.build_runtime_plan(mini_bp, ctx_holder=ctx_holder)

        if execution_context:
            ctx_holder.context = execution_context

        step = rt_plan.get_step(node_uid)

        if step_context:
            step.func.set_context(step_context)

        if bindings is not None:
            self._binder.bind(step.func, bindings)

        return step.func(state, config={})

    def evaluate_condition(
        self,
        condition_rid: str,
        condition_blueprint: Dict[str, Any],
        step_context: Optional[StepContext],
        state: GraphState,
    ) -> str:
        """
        Build a condition from its mini-blueprint, inject context, run it.
        """
        mini_bp = BlueprintSpec.model_validate(condition_blueprint)
        registry = self._factory.build_session_registry(mini_bp)
        condition = registry.get_instance(ResourceCategory.CONDITION, condition_rid)

        if step_context and isinstance(condition, SupportsStepContext):
            condition.set_context(step_context)

        return condition(state)
