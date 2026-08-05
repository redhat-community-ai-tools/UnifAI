"""Temporal activities for ScheduledSessionWorkflow.

Delegates to SessionService and WorkflowScheduleService; maps results
to Temporal DTOs and persists the child workflow handle.
"""
import logging
from datetime import datetime, timezone

from temporalio import activity

from mas.scheduling.service import WorkflowScheduleService
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
        session_manager: UserSessionManager,
        schedule_service: WorkflowScheduleService,
    ) -> None:
        self._session_service = session_service
        self._session_manager = session_manager
        self._schedule_service = schedule_service

    @activity.defn(name="provision_scheduled_session")
    def provision_scheduled_session(self, params: ScheduledSessionParams) -> ProvisionResult:
        """Provision a session and return Temporal workflow params for the child run."""
        session_id = self._session_service.provision_scheduled_session(
            identity=params.identity,
            blueprint_id=params.blueprint_id,
            inputs=params.inputs,
            schedule_id=params.schedule_id,
            credential_user_id=params.credential_user_id,
            dedupe_key=params.dedupe_key,
        )
        self._persist_engine_handle(session_id)
        return self._build_provision_result(session_id)

    @activity.defn(name="record_scheduled_outcome")
    def record_scheduled_outcome(self, params: RecordOutcomeParams) -> None:
        """Record the schedule run outcome after the child workflow finishes."""
        started = self._parse_started_at(params)
        self._schedule_service.record_outcome(
            params.schedule_id, params.session_id, params.outcome, started,
        )

    # ── Private helpers ───────────────────────────────────────────────

    def _persist_engine_handle(self, session_id: str) -> None:
        """Set the session engine_handle to the child SessionWorkflow id."""
        record = self._session_manager.get_record(session_id)
        handle = scheduled_session_workflow_id(session_id)
        if record.engine_handle == handle:
            return
        record.update_context(engine_handle=handle)
        self._session_manager.save_record(record)

    def _build_provision_result(self, session_id: str) -> ProvisionResult:
        """Build a ProvisionResult from a provisioned session."""
        handle = scheduled_session_workflow_id(session_id)
        domain_params = self._session_service.build_scheduled_execution_params(
            session_id,
            engine_name="temporal",
            engine_handle=handle,
        )
        graph_params = GraphExecutionParams(
            state=domain_params.graph_state,
            graph_definition=domain_params.graph_definition,
            session_id=session_id,
            execution_context=domain_params.execution_context,
        )
        workflow_params = SessionWorkflowParams(
            run_id=session_id,
            execution_context=domain_params.execution_context,
            graph_execution_params=graph_params,
        )
        return ProvisionResult(session_id=session_id, params=workflow_params)

    @staticmethod
    def _parse_started_at(params: RecordOutcomeParams) -> datetime:
        """Parse started_at from ISO string; fall back to utcnow on failure."""
        try:
            return datetime.fromisoformat(params.started_at)
        except (ValueError, TypeError):
            logger.warning(
                "Malformed started_at for schedule %s run %s: %r; "
                "falling back to now()",
                params.schedule_id,
                params.session_id,
                params.started_at,
                exc_info=True,
            )
            return datetime.now(timezone.utc)
