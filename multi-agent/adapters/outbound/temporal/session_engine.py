"""
Temporal adapter for background session operations.

Implements the BackgroundSessionEngine port — submit and cancel
session workflows via the Temporal client.

Uses asyncio.run() to bridge from synchronous Flask context
into Temporal's async API.
"""
import asyncio
import uuid
import logging

from mas.session.execution.ports import BackgroundSessionEngine, SubmitSessionRequest
from mas.session.domain.workflow_session import WorkflowSession
from config.app_config import AppConfig
from temporal.client import get_temporal_client
from temporal.models import SessionWorkflowParams, GraphExecutionParams
from outbound.temporal.executor import TemporalGraphExecutor

logger = logging.getLogger(__name__)

_WORKFLOW_NAME = "SessionWorkflow"


class TemporalSessionEngine(BackgroundSessionEngine):
    """
    Temporal implementation of background session operations.

    generate_handle():
      Creates a unique Temporal workflow ID that can be persisted before
      the workflow starts, eliminating race windows.

    submit():
      Starts a durable SessionWorkflow that owns the execution lifecycle
      (begin → execute → complete/fail) inside the Temporal cluster.
      Reads the pre-generated handle from request.execution_context.engine_handle.
      Requires the session's executable_graph to be a TemporalGraphExecutor.

    cancel():
      Sends a cancellation request to the Temporal workflow.  The workflow's
      CancelledError handler triggers the cancel_session activity which owns
      the lifecycle transition and channel cleanup via BackgroundLifecycleHandler.
    """

    def generate_handle(self, session_id: str) -> str:
        return f"session-{session_id}-{uuid.uuid4().hex[:8]}"

    def submit(self, session: WorkflowSession, request: SubmitSessionRequest) -> None:
        asyncio.run(self._start_session_workflow(session, request))

    def cancel(self, handle: str) -> None:
        asyncio.run(self._cancel_workflow(handle))

    async def _start_session_workflow(
        self,
        session: WorkflowSession,
        request: SubmitSessionRequest,
    ) -> None:
        executor = session.executable_graph
        if not isinstance(executor, TemporalGraphExecutor):
            raise TypeError(
                f"TemporalSessionEngine requires a TemporalGraphExecutor, "
                f"got {type(executor).__name__}. "
                f"Ensure the session was built with engine_name='temporal'."
            )

        cfg = AppConfig.get_instance()
        client = await get_temporal_client()

        handle = request.execution_context.engine_handle
        if not handle:
            raise ValueError(
                "engine_handle must be set on execution_context before submit()"
            )

        graph_params = GraphExecutionParams(
            state=session.graph_state,
            graph_definition=executor.graph_definition,
            session_id=session.get_run_id(),
            execution_context=request.execution_context,
        )
        params = SessionWorkflowParams(
            run_id=session.get_run_id(),
            execution_context=request.execution_context,
            graph_execution_params=graph_params,
        )
        await client.start_workflow(
            _WORKFLOW_NAME,
            params,
            id=handle,
            task_queue=cfg.temporal_task_queue,
        )

    async def _cancel_workflow(self, handle: str) -> None:
        client = await get_temporal_client()
        wf_handle = client.get_workflow_handle(handle)
        await wf_handle.cancel()
