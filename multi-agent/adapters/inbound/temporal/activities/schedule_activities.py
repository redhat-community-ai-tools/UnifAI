"""
Schedule activities -- Temporal activities for the ScheduledSessionWorkflow.

Each activity is independently retryable and delegates to domain services
(SessionService, SessionInputProjector, UserSessionManager, WorkflowScheduleService).
"""
import logging
from datetime import datetime, timezone

from temporalio import activity

from mas.core.execution_context import ExecutionContext
from mas.scheduling.service import WorkflowScheduleService
from mas.session.domain.models import SessionMeta
from mas.session.execution.input_projector import SessionInputProjector
from mas.session.management.user_session_manager import UserSessionManager
from mas.session.service import SessionService
from temporal.models import (
    GraphExecutionParams,
    ProvisionResult,
    RecordOutcomeParams,
    ScheduledSessionParams,
    SessionWorkflowParams,
)
from temporal.workflow_ids import scheduled_session_workflow_id

logger = logging.getLogger(__name__)


class ScheduleActivities:
    """Activities for the ScheduledSessionWorkflow."""

    def __init__(
        self,
        session_service: SessionService,
        input_projector: SessionInputProjector,
        session_manager: UserSessionManager,
        schedule_service: WorkflowScheduleService,
    ) -> None:
        self._session_service = session_service
        self._input_projector = input_projector
        self._session_manager = session_manager
        self._schedule_service = schedule_service

    @activity.defn(name="provision_scheduled_session")
    def provision_scheduled_session(self, params: ScheduledSessionParams) -> ProvisionResult:
        """Create session, stage inputs, resolve blueprint, compile graph.

        Deduplication via dedupe_key ensures idempotency on retry.
        """
        if params.dedupe_key:
            try:
                self._session_manager.get_record(params.dedupe_key)
            except KeyError:
                pass
            else:
                self._persist_engine_handle(params.dedupe_key)
                return self._build_provision_result(params.dedupe_key)

        metadata = SessionMeta(
            source="schedule",
            schedule_id=params.schedule_id,
            prompt_text=params.text,
        )

        session_id, _session = self._session_service.prepare_for_scheduled_execution(
            identity=params.identity,
            blueprint_id=params.blueprint_id,
            inputs=params.inputs,
            text=params.text,
            metadata=metadata,
            logged_in_user=params.credential_user_id,
            run_id=params.dedupe_key,
        )
        self._persist_engine_handle(session_id)

        return self._build_provision_result(session_id)

    @activity.defn(name="record_scheduled_outcome")
    def record_scheduled_outcome(self, params: RecordOutcomeParams) -> None:
        """Record run outcome in the schedule aggregate and handle finite-schedule completion."""
        try:
            started = datetime.fromisoformat(params.started_at)
        except (ValueError, TypeError):
            logger.warning(
                "Malformed started_at for schedule %s run %s: %r; "
                "falling back to now()",
                params.schedule_id,
                params.session_id,
                params.started_at,
                exc_info=True,
            )
            started = datetime.now(timezone.utc)

        self._schedule_service.record_run(
            params.schedule_id, params.session_id, params.outcome, started,
        )
        self._schedule_service.mark_completed(params.schedule_id)

    # ── Private helpers ───────────────────────────────────────────────

    def _persist_engine_handle(self, session_id: str) -> None:
        """Persist the child SessionWorkflow ID as the session engine_handle."""
        record = self._session_manager.get_record(session_id)
        handle = scheduled_session_workflow_id(session_id)
        if record.engine_handle == handle:
            return
        record.update_context(engine_handle=handle)
        self._session_manager.save_record(record)

    def _build_provision_result(self, run_id: str) -> ProvisionResult:
        """Build ProvisionResult from a hydrated session."""
        session = self._session_manager.get_session(run_id)
        executor = session.executable_graph
        exec_context = ExecutionContext(
            session_id=run_id,
            identity=session.record.identity,
            scope="public",
            engine_name="temporal",
            engine_handle=scheduled_session_workflow_id(run_id),
            tags=session.record.run_context.tags,
        )
        graph_params = GraphExecutionParams(
            state=session.graph_state,
            graph_definition=executor.graph_definition,
            session_id=run_id,
            execution_context=exec_context,
        )
        workflow_params = SessionWorkflowParams(
            run_id=run_id,
            execution_context=exec_context,
            graph_execution_params=graph_params,
        )
        return ProvisionResult(session_id=run_id, params=workflow_params)
