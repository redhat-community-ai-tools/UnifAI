"""
Scheduled session workflow -- triggered by Temporal Schedule on each tick.

Creates a fresh session, stages inputs, builds workflow params via activity
(blueprint resolution), then delegates to SessionWorkflow as a child.
After the child completes (or fails), a post_execution activity records the
run outcome in the prompt aggregate and handles finite-schedule completion.
"""
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from mas.graph.state.graph_state import GraphState
from temporal.models import (
    BuildSessionWorkflowParamsInput,
    PostExecutionParams,
    RunOutcome,
    ScheduledSessionParams,
    SessionWorkflowParams,
    StageScheduledInputsParams,
)

with workflow.unsafe.imports_passed_through():
    from inbound.temporal.workflows.session_workflow import SessionWorkflow

_ACTIVITY_TIMEOUT = timedelta(seconds=30)
_BUILD_PARAMS_TIMEOUT = timedelta(minutes=2)
_ACTIVITY_RETRY = RetryPolicy(maximum_attempts=3)
_CHILD_EXECUTION_TIMEOUT = timedelta(hours=4)


@workflow.defn
class ScheduledSessionWorkflow:
    """
    Parent workflow for scheduled session execution.

    Each schedule tick starts one instance. Steps:
    1. create_scheduled_session -- new SessionRecord in Mongo (PENDING)
    2. stage_scheduled_inputs -- apply inputs + prompt text (QUEUED)
    3. build_session_workflow_params -- resolve blueprint, compile graph
    4. SessionWorkflow (child) -- full lifecycle (begin -> execute -> complete/fail)
    5. post_execution -- record run stats, conditionally complete finite schedules
    """

    @workflow.run
    async def run(self, params: ScheduledSessionParams) -> str:
        run_id = await workflow.execute_activity(
            "create_scheduled_session",
            params,
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_ACTIVITY_RETRY,
        )

        started_at = workflow.now().isoformat()

        await workflow.execute_activity(
            "stage_scheduled_inputs",
            StageScheduledInputsParams(
                run_id=run_id,
                inputs=params.inputs,
                text=params.text,
            ),
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_ACTIVITY_RETRY,
        )

        session_params = await workflow.execute_activity(
            "build_session_workflow_params",
            BuildSessionWorkflowParamsInput(run_id=run_id),
            start_to_close_timeout=_BUILD_PARAMS_TIMEOUT,
            retry_policy=_ACTIVITY_RETRY,
            result_type=SessionWorkflowParams,
        )

        outcome = RunOutcome.COMPLETED
        try:
            await workflow.execute_child_workflow(
                SessionWorkflow.run,
                session_params,
                id=f"sched-session-{run_id}",
                execution_timeout=_CHILD_EXECUTION_TIMEOUT,
                result_type=GraphState,
            )
        except Exception:
            outcome = RunOutcome.FAILED

        await workflow.execute_activity(
            "post_execution",
            PostExecutionParams(
                prompt_id=params.prompt_id,
                run_id=run_id,
                status=outcome,
                started_at=started_at,
            ),
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_ACTIVITY_RETRY,
        )

        return run_id
