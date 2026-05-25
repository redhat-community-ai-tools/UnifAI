"""
Temporal workflow for graph traversal — inbound adapter.

Defines the @workflow.defn for Temporal registration.
Delegates graph traversal logic to engine.distributed.traversal.GraphTraversal.
Activity calls remain explicit here (Temporal requires direct await on
workflow.execute_activity for deterministic replay).

pydantic_data_converter handles GraphState serialization/deserialization
automatically — no manual .serialize()/.deserialize() calls needed.
"""
from datetime import timedelta
from typing import Any, Dict, List

from temporalio import workflow
from temporalio.common import RetryPolicy

from mas.engine.domain.models import GraphDefinition, ConditionalEdgeDef
from mas.engine.distributed.traversal import GraphTraversal
from mas.graph.state.graph_state import GraphState
from temporal.models import (
    GraphExecutionParams,
    ExecuteNodeParams,
    EvaluateConditionParams,
)

_NODE_TIMEOUT = timedelta(minutes=15)
_NODE_HEARTBEAT = timedelta(seconds=10)
_NODE_RETRY = RetryPolicy(maximum_attempts=3)

_CONDITION_TIMEOUT = timedelta(seconds=30)
_CONDITION_RETRY = RetryPolicy(maximum_attempts=2)


@workflow.defn
class GraphTraversalWorkflow:
    """
    Thin Temporal workflow that wires activity calls into the
    engine-level GraphTraversal algorithm.
    """

    def __init__(self) -> None:
        self._state: Dict[str, Any] = {}
        self._current_nodes: List[str] = []
        self._session_id: str = ""
        self._execution_context = None

    @workflow.run
    async def run(self, params: GraphExecutionParams) -> GraphState:
        graph = params.graph_definition
        state = params.state
        self._session_id = params.session_id
        self._execution_context = params.execution_context

        traversal = GraphTraversal(graph, GraphState)

        final_state = await traversal.run(
            initial_state=state,
            execute_node=self._execute_node,
            evaluate_condition=self._evaluate_condition,
            on_superstep=self._on_superstep,
        )

        self._state = final_state.serialize()
        self._current_nodes = []
        return final_state

    @workflow.query
    def get_state(self) -> dict:
        return self._state

    @workflow.query
    def get_current_nodes(self) -> List[str]:
        return self._current_nodes

    def _on_superstep(self, step, active_nodes, state):
        self._current_nodes = sorted(active_nodes)
        self._state = state.serialize()

    async def _execute_node(
        self,
        uid: str,
        state: GraphState,
        graph: GraphDefinition,
    ) -> GraphState:
        node_def = graph.nodes[uid]
        params = ExecuteNodeParams(
            node_uid=uid,
            node_blueprint=node_def.node_blueprint,
            step_context=node_def.step_context,
            state=state,
            session_id=self._session_id,
            execution_context=self._execution_context,
        )
        return await workflow.execute_activity(
            "execute_graph_node",
            params,
            start_to_close_timeout=_NODE_TIMEOUT,
            heartbeat_timeout=_NODE_HEARTBEAT,
            retry_policy=_NODE_RETRY,
            result_type=GraphState,
        )

    async def _evaluate_condition(
        self,
        state: GraphState,
        cond: ConditionalEdgeDef,
    ) -> str:
        params = EvaluateConditionParams(
            condition_rid=cond.condition_rid,
            condition_blueprint=cond.condition_blueprint,
            step_context=cond.step_context,
            state=state,
        )
        return await workflow.execute_activity(
            "evaluate_condition",
            params,
            start_to_close_timeout=_CONDITION_TIMEOUT,
            retry_policy=_CONDITION_RETRY,
        )
