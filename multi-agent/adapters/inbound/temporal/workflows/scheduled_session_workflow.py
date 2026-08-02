"""
Scheduled session workflow -- triggered by Temporal Schedule on each tick.

Implements ScheduledRunOps; ScheduledSessionRunner owns the
provision → execute → record ordering.
"""
import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ChildWorkflowError, is_cancelled_exception

from mas.graph.state.graph_state import GraphState
from mas.scheduling.models import RunOutcome
from mas.session.domain.exceptions import ScheduledSessionCancelledException
from mas.session.execution.ports import ScheduledExecutionParams
from mas.session.execution.scheduled_runner import ScheduledSessionRunner
from temporal.models import (
    ProvisionResult,
    RecordOutcomeParams,
    ScheduledSessionParams,
    SessionWorkflowParams,
)
from temporal.workflow_ids import scheduled_session_workflow_id
from inbound.temporal.workflows.session_workflow import SessionWorkflow

_PROVISION_TIMEOUT = timedelta(minutes=2)
_RECORD_TIMEOUT = timedelta(seconds=30)
_ACTIVITY_RETRY = RetryPolicy(maximum_attempts=3)
_CHILD_EXECUTION_TIMEOUT = timedelta(hours=4)


@workflow.defn
class ScheduledSessionWorkflow:
    """Parent workflow for one schedule tick; implements ScheduledRunOps."""

    @workflow.run
    async def run(self, params: ScheduledSessionParams) -> str:
        self._params = params
        self._started_at = workflow.now().isoformat()
        self._dedupe_key = str(workflow.uuid4())

        runner = ScheduledSessionRunner()
        try:
            return await runner.run(self)
        except ScheduledSessionCancelledException:
            raise asyncio.CancelledError()
        except asyncio.CancelledError:
            raise

    # ── ScheduledRunOps implementation ────────────────────────────────

    async def provision(self) -> tuple[str, ScheduledExecutionParams]:
        """Create session, stage inputs, resolve blueprint in one activity."""
        deduped_params = self._params.model_copy(
            update={"dedupe_key": self._dedupe_key}
        )
        result: ProvisionResult = await workflow.execute_activity(
            "provision_scheduled_session",
            deduped_params,
            start_to_close_timeout=_PROVISION_TIMEOUT,
            retry_policy=_ACTIVITY_RETRY,
            result_type=ProvisionResult,
        )
        return result.session_id, result.params.to_scheduled_execution_params()

    async def execute(self, params: ScheduledExecutionParams) -> RunOutcome:
        """Run the session as a child workflow.

        Translate Temporal cancellation (parent or child) into
        ScheduledSessionCancelledException.
        """
        workflow_params = SessionWorkflowParams.from_scheduled_execution_params(params)
        child_id = scheduled_session_workflow_id(workflow_params.run_id)
        try:
            await workflow.execute_child_workflow(
                SessionWorkflow.run,
                workflow_params,
                id=child_id,
                execution_timeout=_CHILD_EXECUTION_TIMEOUT,
                result_type=GraphState,
            )
            return RunOutcome.COMPLETED
        except asyncio.CancelledError:
            raise ScheduledSessionCancelledException()
        except ChildWorkflowError as e:
            if is_cancelled_exception(e):
                workflow.logger.info(
                    "Child workflow %s cancelled — propagating to parent tick",
                    child_id,
                )
                raise ScheduledSessionCancelledException() from e
            workflow.logger.error(
                "Child workflow %s failed: %s",
                child_id, e,
            )
            return RunOutcome.FAILED
        except Exception as e:
            workflow.logger.error(
                "Child workflow %s failed: %s",
                child_id, e,
            )
            return RunOutcome.FAILED

    async def record(
        self,
        session_id: str,
        outcome: RunOutcome,
        failure_reason: Optional[str],
    ) -> None:
        """Record outcome via activity, shielded from cancellation."""
        try:
            await asyncio.shield(
                workflow.execute_activity(
                    "record_scheduled_outcome",
                    RecordOutcomeParams(
                        schedule_id=self._params.schedule_id,
                        session_id=session_id,
                        outcome=outcome,
                        started_at=self._started_at,
                        failure_reason=failure_reason,
                    ),
                    start_to_close_timeout=_RECORD_TIMEOUT,
                    retry_policy=_ACTIVITY_RETRY,
                )
            )
        except asyncio.CancelledError:
            pass
