"""
Temporal session workflow — inbound adapter (parent workflow).

Implements BackgroundSessionOps with Temporal-specific mechanics
(activities, child workflows) and delegates the canonical lifecycle
ordering to BackgroundSessionRunner.

The ordering rule (begin → execute → complete/fail/cancel) lives in
session/execution/background_runner.py — NOT here.  This file
only supplies the HOW for each step.

Inputs are already staged into the SessionRecord before this workflow
starts.  begin() only transitions QUEUED → RUNNING.

pydantic_data_converter handles GraphState serialization/deserialization
automatically — no manual .serialize()/.deserialize() calls needed.
"""
import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import is_cancelled_exception

from mas.graph.state.graph_state import GraphState
from mas.session.domain.exceptions import SessionCancelledException
from mas.session.execution.background_runner import BackgroundSessionRunner
from temporal.models import (
    SessionWorkflowParams,
    GraphExecutionParams,
    BeginSessionParams,
    CompleteSessionParams,
    FailSessionParams,
    CancelSessionParams,
)
from inbound.temporal.workflows.graph_traversal_workflow import GraphTraversalWorkflow

_LIFECYCLE_TIMEOUT = timedelta(seconds=30)
_LIFECYCLE_RETRY = RetryPolicy(maximum_attempts=3)

_GRAPH_WORKFLOW_TIMEOUT = timedelta(hours=1)


@workflow.defn
class SessionWorkflow:
    """
    Parent workflow for fire-and-forget session execution.

    Implements BackgroundSessionOps (structural typing via Protocol).
    Each method maps to a Temporal activity or child workflow.
    The runner drives the canonical ordering including cancel.
    """

    @workflow.run
    async def run(self, params: SessionWorkflowParams) -> GraphState:
        self._params = params
        runner = BackgroundSessionRunner()
        try:
            return await runner.run(self)
        except SessionCancelledException:
            raise asyncio.CancelledError()
        except asyncio.CancelledError:
            # Edge case: raw CancelledError arrived during begin()/complete()
            # before execute_graph() could translate it.
            await self.cancel()
            raise

    # ── BackgroundSessionOps implementation ──────────────────────────

    async def begin(self) -> GraphState:
        """Mark RUNNING, bind context, persist. Returns staged GraphState."""
        return await workflow.execute_activity(
            "begin_session",
            BeginSessionParams(
                run_id=self._params.run_id,
                execution_context=self._params.execution_context,
            ),
            start_to_close_timeout=_LIFECYCLE_TIMEOUT,
            retry_policy=_LIFECYCLE_RETRY,
            result_type=GraphState,
        )

    async def execute_graph(self, seeded_state: GraphState) -> GraphState:
        """Run graph traversal as a child workflow.

        Translates Temporal-wrapped cancellation (ChildWorkflowError →
        CancelledError) into SessionCancelledException at the adapter
        boundary so the runner can call ops.cancel().
        """
        graph_params = GraphExecutionParams(
            state=seeded_state,
            graph_definition=self._params.graph_execution_params.graph_definition,
            session_id=self._params.run_id,
            execution_context=self._params.execution_context,
        )
        try:
            return await workflow.execute_child_workflow(
                GraphTraversalWorkflow.run,
                graph_params,
                id=f"{workflow.info().workflow_id}-graph",
                execution_timeout=_GRAPH_WORKFLOW_TIMEOUT,
                result_type=GraphState,
            )
        except Exception as e:
            if is_cancelled_exception(e):
                raise SessionCancelledException() from e
            raise

    async def complete(self, final_state: GraphState) -> None:
        """Attach final state, mark COMPLETED, persist."""
        await workflow.execute_activity(
            "complete_session",
            CompleteSessionParams(
                run_id=self._params.run_id,
                final_state=final_state,
            ),
            start_to_close_timeout=_LIFECYCLE_TIMEOUT,
            retry_policy=_LIFECYCLE_RETRY,
        )

    async def fail(self, error: Exception) -> None:
        """Mark FAILED, persist."""
        await workflow.execute_activity(
            "fail_session",
            FailSessionParams(
                run_id=self._params.run_id,
                error_message=str(error),
            ),
            start_to_close_timeout=_LIFECYCLE_TIMEOUT,
            retry_policy=_LIFECYCLE_RETRY,
        )

    async def cancel(self) -> None:
        """Mark CANCELLED, close channels, persist."""
        await workflow.execute_activity(
            "cancel_session",
            CancelSessionParams(run_id=self._params.run_id),
            start_to_close_timeout=_LIFECYCLE_TIMEOUT,
            retry_policy=_LIFECYCLE_RETRY,
        )
