"""
Stateless node execution logic for distributed engines.

Rebuilds a single node (or condition) from its mini-blueprint,
injects the real StepContext, runs it, and discards it.
Like a Flask handler — any worker can execute any node.

If a pre-built SessionChannel is provided, it is injected into
streaming-capable nodes so background workers can emit events.
"""
from typing import Any, Dict, Optional

from mas.blueprints.models.blueprint import BlueprintSpec
from mas.core.channels import SessionChannel
from mas.core.enums import ResourceCategory
from mas.core.execution_context import ExecutionContext, ExecutionContextHolder
from mas.graph.models.step_context import StepContext
from mas.graph.state.graph_state import GraphState
from mas.session.building.workflow_session_factory import WorkflowSessionFactory


class NodeExecutor:
    """
    Stateless executor for individual graph nodes and conditions.

    Created once at worker startup with a shared session factory.
    Each call builds a fresh node from the mini-blueprint, injects
    context, runs it, and returns the result.

    Channel creation is NOT this class's concern — callers provide
    a ready-to-use SessionChannel when streaming is needed.
    """

    def __init__(self, session_factory: WorkflowSessionFactory) -> None:
        self._factory = session_factory

    def execute_node(
        self,
        node_uid: str,
        node_blueprint: Dict[str, Any],
        step_context: Optional[StepContext],
        state: GraphState,
        channel: Optional[SessionChannel] = None,
        execution_context: Optional[ExecutionContext] = None,
    ) -> GraphState:
        """
        Build ONE node from its mini-blueprint, inject context, run it.

        If a channel is provided, it is injected into the node so that
        streaming-capable nodes can emit events during execution.
        """
        mini_bp = BlueprintSpec.model_validate(node_blueprint)

        ctx_holder = ExecutionContextHolder()
        rt_plan = self._factory.build_runtime_plan(mini_bp, ctx_holder=ctx_holder)

        if execution_context:
            ctx_holder.context = execution_context

        step = rt_plan.get_step(node_uid)

        if step_context:
            step.func.set_context(step_context)

        if channel and hasattr(step.func, "set_streaming_channel"):
            step.func.set_streaming_channel(channel)

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

        if step_context and hasattr(condition, 'set_context'):
            condition.set_context(step_context)

        return condition(state)
