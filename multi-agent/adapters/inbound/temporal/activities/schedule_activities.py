"""
Schedule activities -- Temporal activities for the ScheduledSessionWorkflow.

Each activity is independently retryable. The activities delegate to
existing domain services (SessionService, SessionInputProjector,
UserSessionManager, PromptService).
"""
import logging

from temporalio import activity

from mas.core.execution_context import ExecutionContext
from mas.session.domain.models import SessionMeta
from temporal.models import (
    BuildSessionWorkflowParamsInput,
    GraphExecutionParams,
    PostExecutionParams,
    ScheduledSessionParams,
    SessionWorkflowParams,
    StageScheduledInputsParams,
)

logger = logging.getLogger(__name__)


class ScheduleActivities:
    """Activities for the ScheduledSessionWorkflow."""

    def __init__(
        self,
        session_service,
        input_projector,
        session_manager,
        prompt_service,
    ):
        self._session_service = session_service
        self._input_projector = input_projector
        self._session_manager = session_manager
        self._prompt_service = prompt_service

    @activity.defn(name="create_scheduled_session")
    def create_scheduled_session(self, params: ScheduledSessionParams) -> str:
        if params.idempotency_key:
            try:
                self._session_manager.get_record(params.idempotency_key)
                return params.idempotency_key
            except KeyError:
                pass

        metadata = SessionMeta(
            source="schedule",
            schedule_id=params.prompt_id,
            prompt_text=params.text,
        )
        return self._session_service.create(
            identity=params.identity,
            blueprint_id=params.blueprint_id,
            metadata=metadata,
            run_id=params.idempotency_key,
        )

    @activity.defn(name="stage_scheduled_inputs")
    def stage_scheduled_inputs(self, params: StageScheduledInputsParams) -> None:
        record = self._session_manager.get_record(params.run_id)
        inputs = {**params.inputs}
        if params.text:
            inputs["user_prompt"] = params.text
        self._input_projector.apply(record, inputs)

    @activity.defn(name="build_session_workflow_params")
    def build_session_workflow_params(
        self, params: BuildSessionWorkflowParamsInput,
    ) -> SessionWorkflowParams:
        """Resolve blueprint + compile graph, return SessionWorkflowParams.

        Mirrors TemporalSessionEngine._start_session_workflow() but runs
        inside the worker (activity context) rather than Flask.
        """
        session = self._session_manager.get_session(params.run_id)
        executor = session.executable_graph

        exec_context = ExecutionContext(
            session_id=params.run_id,
            identity=session.record.identity,
            scope="public",
            engine_name="temporal",
        )

        graph_params = GraphExecutionParams(
            state=session.graph_state,
            graph_definition=executor.graph_definition,
            session_id=params.run_id,
            execution_context=exec_context,
        )
        return SessionWorkflowParams(
            run_id=params.run_id,
            execution_context=exec_context,
            graph_execution_params=graph_params,
        )

    @activity.defn(name="post_execution")
    def post_execution(self, params: PostExecutionParams) -> None:
        from datetime import datetime, timezone
        try:
            started = datetime.fromisoformat(params.started_at)
        except (ValueError, TypeError):
            logger.warning(
                "Malformed started_at for prompt %s run %s: %r; "
                "falling back to now()",
                params.prompt_id,
                params.run_id,
                params.started_at,
                exc_info=True,
            )
            started = datetime.now(timezone.utc)

        self._prompt_service.record_run(
            params.prompt_id, params.run_id, params.status, started,
        )
        self._prompt_service.mark_completed(params.prompt_id)
