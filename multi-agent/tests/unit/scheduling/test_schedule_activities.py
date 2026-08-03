"""Unit tests for ScheduleActivities.

Covers: provision_scheduled_session, record_scheduled_outcome.
"""
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from mas.core.identity import Identity
from temporal.models import (
    GraphExecutionParams,
    RecordOutcomeParams,
    RunOutcome,
    ScheduledSessionParams,
    SessionWorkflowParams,
)


@pytest.fixture
def identity():
    return Identity.user("user-1")


def _make_mock_session():
    """Build a session mock that carries real-enough Pydantic-compatible fields."""
    session = Mock()
    session.record = Mock()
    session.record.identity = Identity.user("user-1")
    session.record.run_context = Mock()
    session.record.run_context.tags = {}
    session.executable_graph = Mock()
    session.executable_graph.graph_definition = {"nodes": {}, "edges": {}}
    session.graph_state = {"inputs": {}, "outputs": {}}
    return session


@pytest.fixture
def mock_session_service():
    svc = Mock()
    session = _make_mock_session()
    svc.prepare_for_scheduled_execution.return_value = ("session-abc-123", session)
    return svc


@pytest.fixture
def mock_input_projector():
    return Mock()


@pytest.fixture
def mock_session_manager():
    mgr = Mock()
    session = _make_mock_session()
    mgr.get_session.return_value = session

    record = Mock()
    record.engine_handle = None

    def get_record(run_id):
        # Dedup hit for explicitly existing sessions; create path uses
        # the prepared session id; anything else is a miss.
        if run_id in ("existing-session", "session-abc-123"):
            return record
        raise KeyError(run_id)

    mgr.get_record.side_effect = get_record
    return mgr


@pytest.fixture
def mock_schedule_service():
    return Mock()


@pytest.fixture
def activities(mock_session_service, mock_input_projector, mock_session_manager, mock_schedule_service):
    from inbound.temporal.activities.schedule_activities import ScheduleActivities
    return ScheduleActivities(
        session_service=mock_session_service,
        input_projector=mock_input_projector,
        session_manager=mock_session_manager,
        schedule_service=mock_schedule_service,
    )


# ═══════════════════════════════════════════════════════════════════
# provision_scheduled_session
# ═══════════════════════════════════════════════════════════════════

class TestProvisionScheduledSession:
    def test_creates_session_via_service(
        self, activities, mock_session_service, mock_session_manager, identity,
    ):
        params = ScheduledSessionParams(
            schedule_id="sched-1",
            blueprint_id="bp-1",
            identity=identity,
            text="Generate report",
            dedupe_key="dedup-1",
        )
        result = activities.provision_scheduled_session(params)
        assert result.session_id == "session-abc-123"
        call_kwargs = mock_session_service.prepare_for_scheduled_execution.call_args[1]
        assert call_kwargs["identity"] == identity
        assert call_kwargs["blueprint_id"] == "bp-1"
        assert call_kwargs["text"] == "Generate report"
        meta = call_kwargs["metadata"]
        assert meta.source == "schedule"
        assert meta.schedule_id == "sched-1"
        mock_session_manager.save_record.assert_called_once()
        assert result.params.execution_context.engine_handle == (
            "sched-session-session-abc-123"
        )

    def test_dedup_returns_existing_session(
        self, activities, mock_session_manager, mock_session_service, identity,
    ):
        params = ScheduledSessionParams(
            schedule_id="sched-1",
            blueprint_id="bp-1",
            identity=identity,
            dedupe_key="existing-session",
        )
        result = activities.provision_scheduled_session(params)
        assert result.session_id == "existing-session"
        mock_session_service.prepare_for_scheduled_execution.assert_not_called()
        mock_session_manager.save_record.assert_called_once()

    def test_returns_workflow_params(self, activities, identity):
        params = ScheduledSessionParams(
            schedule_id="sched-1",
            blueprint_id="bp-1",
            identity=identity,
            dedupe_key="dedup-2",
        )
        result = activities.provision_scheduled_session(params)
        assert result.params is not None
        assert result.params.run_id == "session-abc-123"

    def test_skips_save_when_engine_handle_already_set(
        self, activities, mock_session_manager, identity,
    ):
        record = mock_session_manager.get_record("session-abc-123")
        record.engine_handle = "sched-session-session-abc-123"
        params = ScheduledSessionParams(
            schedule_id="sched-1",
            blueprint_id="bp-1",
            identity=identity,
            dedupe_key="dedup-3",
        )
        activities.provision_scheduled_session(params)
        mock_session_manager.save_record.assert_not_called()


# ═══════════════════════════════════════════════════════════════════
# record_scheduled_outcome
# ═══════════════════════════════════════════════════════════════════

class TestRecordScheduledOutcome:
    def test_records_run(self, activities, mock_schedule_service):
        params = RecordOutcomeParams(
            schedule_id="sched-1",
            session_id="session-1",
            outcome=RunOutcome.COMPLETED,
            started_at="2026-07-20T10:00:00+00:00",
        )
        activities.record_scheduled_outcome(params)
        mock_schedule_service.record_run.assert_called_once()
        call_args = mock_schedule_service.record_run.call_args[0]
        assert call_args[0] == "sched-1"
        assert call_args[1] == "session-1"
        assert call_args[2] == RunOutcome.COMPLETED

    def test_calls_mark_completed(self, activities, mock_schedule_service):
        params = RecordOutcomeParams(
            schedule_id="sched-1",
            session_id="session-1",
            outcome=RunOutcome.COMPLETED,
            started_at="2026-07-20T10:00:00+00:00",
        )
        activities.record_scheduled_outcome(params)
        mock_schedule_service.mark_completed.assert_called_once_with("sched-1")

    def test_parses_started_at_from_iso(self, activities, mock_schedule_service):
        params = RecordOutcomeParams(
            schedule_id="sched-1",
            session_id="session-1",
            outcome=RunOutcome.COMPLETED,
            started_at="2026-07-20T10:30:00+00:00",
        )
        activities.record_scheduled_outcome(params)
        started = mock_schedule_service.record_run.call_args[0][3]
        assert isinstance(started, datetime)
        assert started.hour == 10
        assert started.minute == 30

    def test_invalid_started_at_falls_back_to_now(self, activities, mock_schedule_service):
        params = RecordOutcomeParams(
            schedule_id="sched-1",
            session_id="session-1",
            outcome=RunOutcome.FAILED,
            started_at="not-a-date",
        )
        activities.record_scheduled_outcome(params)
        started = mock_schedule_service.record_run.call_args[0][3]
        assert isinstance(started, datetime)
        assert (datetime.now(timezone.utc) - started).total_seconds() < 5
