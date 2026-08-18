"""
Temporal graph executor.

Starts a GraphTraversalWorkflow on the shared Temporal task queue
and blocks until the result is ready.  This is the graph-execution
adapter — it knows nothing about session lifecycle.

Uses string-based workflow invocation to avoid importing from the
inbound adapter layer (hexagonal boundary compliance).

pydantic_data_converter handles GraphState serialization/deserialization
automatically — no manual .serialize()/.deserialize() calls needed.
"""
import asyncio
import uuid
from typing import Any

from mas.engine.domain.base_executor import BaseGraphExecutor
from mas.engine.domain.models import GraphDefinition
from mas.graph.state.graph_state import GraphState
from config.app_config import AppConfig
from temporal.client import get_temporal_client
from temporal.models import GraphExecutionParams
from global_utils.utils.logging_config import get_request_id

_WORKFLOW_NAME = "GraphTraversalWorkflow"


class TemporalGraphExecutor(BaseGraphExecutor):
    """
    Executes a graph via Temporal workflows.

    Holds only the GraphDefinition. Workers pick up activities and
    rebuild nodes from the mini-blueprints stored in each NodeDef.
    """

    def __init__(self, graph_def: GraphDefinition) -> None:
        self._graph_def = graph_def
        self._workflow_id: str | None = None

    @property
    def graph_definition(self) -> GraphDefinition:
        return self._graph_def

    def run(self, initial_state: GraphState, *, session_id: str = "") -> GraphState:
        return asyncio.run(self._execute(initial_state, session_id=session_id))

    def get_state(self) -> Any:
        if not self._workflow_id:
            return None
        return asyncio.run(self._query_state())

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    async def _execute(self, state: GraphState, *, session_id: str = "") -> GraphState:
        """Start GraphTraversalWorkflow and block until it completes."""
        cfg = AppConfig.get_instance()
        client = await get_temporal_client()

        workflow_id = f"graph-{uuid.uuid4().hex[:12]}"
        self._workflow_id = workflow_id

        params = GraphExecutionParams(
            state=state,
            graph_definition=self._graph_def,
            session_id=session_id,
            request_id=get_request_id(),
        )
        return await client.execute_workflow(
            _WORKFLOW_NAME,
            params,
            id=workflow_id,
            task_queue=cfg.temporal_task_queue,
        )

    async def _query_state(self) -> dict:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(self._workflow_id)
        return await handle.query("get_state")
