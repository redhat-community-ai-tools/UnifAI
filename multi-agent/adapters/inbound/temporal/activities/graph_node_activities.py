"""
Temporal activity wrapper for graph node and condition execution.

Composes a channel from the factory (adapter wiring) and delegates
the actual execution to the domain-level NodeExecutor.

Builds a ``NodeRuntimeBindings`` value object (channel + HITL) and
passes it to the executor, which uses ``NodeRuntimeBinder`` to
inject capabilities via protocol checks.

The @heartbeat decorator sends periodic heartbeats while the sync
activity body runs.  Cancellation is handled at the workflow level.

pydantic_data_converter handles GraphState serialization/deserialization
automatically — no manual .serialize()/.deserialize() calls needed.
"""
from typing import Any, Optional

from temporalio import activity

from mas.core.channels import ChannelFactory
from mas.core.hitl.ports import ApprovalGateFactory
from mas.core.runtime_binder import NodeRuntimeBindings
from mas.engine.distributed.node_executor import NodeExecutor
from mas.graph.state.graph_state import GraphState
from mas.core.tracing.service import TracingService
from inbound.temporal.activities.heartbeat import heartbeat
from temporal.models import ExecuteNodeParams, EvaluateConditionParams


class GraphNodeActivities:
    """
    Thin adapter — composes a channel from the factory (wiring)
    and delegates node execution to the domain NodeExecutor.

    Builds a ``NodeRuntimeBindings`` that carries the channel and
    HITL gate/policy (when available) as a single value object.
    Gate construction is delegated to ``ApprovalGateFactory``.
    """

    def __init__(
        self,
        node_executor: NodeExecutor,
        channel_factory: Optional[ChannelFactory] = None,
        gate_factory: Optional[ApprovalGateFactory] = None,
        tracing_service: Optional[TracingService] = None,
    ) -> None:
        self._executor = node_executor
        self._channel_factory = channel_factory
        self._gate_factory = gate_factory
        if not tracing_service:
            from mas.core.tracing.noop import NoOpTracingService
            tracing_service = NoOpTracingService()
        self._tracing = tracing_service

    @activity.defn(name="execute_graph_node")
    @heartbeat(interval=3)
    def execute_node(self, params: ExecuteNodeParams) -> GraphState:
        bindings = self._build_bindings(params.session_id)

        user_id = ""
        if params.execution_context:
            user_id = getattr(params.execution_context, "identity_id", "") or ""

        with self._tracing.trace_session(
            session_id=params.session_id,
            user_id=user_id,
            metadata={"node_uid": params.node_uid},
        ):
            try:
                result = self._executor.execute_node(
                    node_uid=params.node_uid,
                    node_blueprint=params.node_blueprint,
                    step_context=params.step_context,
                    state=params.state,
                    bindings=bindings,
                    execution_context=params.execution_context,
                )
            finally:
                self._tracing.flush()
                if self._gate_factory is not None:
                    self._gate_factory.remove(params.session_id)

        return result

    @activity.defn(name="evaluate_condition")
    def evaluate_condition(self, params: EvaluateConditionParams) -> str:
        return self._executor.evaluate_condition(
            condition_rid=params.condition_rid,
            condition_blueprint=params.condition_blueprint,
            step_context=params.step_context,
            state=params.state,
        )

    # ── Bindings construction ────────────────────────────────────

    def _build_bindings(self, session_id: str) -> Optional[NodeRuntimeBindings]:
        """Build a ``NodeRuntimeBindings`` from the channel factory.

        Returns ``None`` when no channel factory is configured.
        """
        if not self._channel_factory or not session_id:
            return None

        gate = None
        policy = None

        channel = self._channel_factory.create_input_capable(session_id)
        if channel is not None:
            if self._gate_factory is not None:
                gate, policy = self._gate_factory.create(
                    channel=channel,
                    session_metadata=None,
                    run_id=session_id,
                )
        else:
            channel = self._channel_factory.create(session_id)

        return NodeRuntimeBindings(
            channel=channel,
            approval_gate=gate,
            approval_policy=policy,
        )
