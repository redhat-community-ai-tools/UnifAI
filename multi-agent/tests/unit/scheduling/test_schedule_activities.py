"""Unit tests for ScheduleActivities.

Covers: provision_scheduled_session, record_scheduled_outcome.
"""
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from mas.core.execution_context import ExecutionContext
from mas.core.identity import Identity
from mas.session.execution.ports import ScheduledExecutionParams
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


def _make_scheduled_execution_params(session_id: str = "session-abc-123"):
    """Build a ScheduledExecutionParams matching what the service would return."""
    return ScheduledExecutionParams(
        run_id=session_id,
        execution_context=ExecutionContext(
            session_id=session_id,
            identity=Identity.user("user-1"),
            scope="public",
            engine_name="temporal",
            engine_handle=f"sched-session-{session_id}",
            tags={},
        ),
        graph_state={"inputs": {}, "outputs": {}},
        graph_definition={"nodes": {}, "edges": {}},
    )


@pytest.fixture
def mock_session_service():
    svc = Mock()
    svc.provision_scheduled_session.return_value = "session-abc-123"
    svc.build_scheduled_execution_params.return_value = _make_scheduled_execution_params()
    return svc


@pytest.fixture
def mock_session_manager():
    mgr = Mock()

    record = Mock()
    record.engine_handle = None

    def get_record(run_id):
        if run_id in ("existing-session", "session-abc-123"):
            return record
        raise KeyError(run_id)

    mgr.get_record.side_effect = get_record
    return mgr


@pytest.fixture
def mock_schedule_service():
    return Mock()


@pytest.fixture
def activities(mock_session_service, mock_session_manager, mock_schedule_service):
    from inbound.temporal.activities.schedule_activities import ScheduleActivities
    return ScheduleActivities(
        session_service=mock_session_service,
        session_manager=mock_session_manager,
        schedule_service=mock_schedule_service,
    )


# ═══════════════════════════════════════════════════════════════════
# provision_scheduled_session
# ═══════════════════════════════════════════════════════════════════

class TestProvisionScheduledSession:
    def test_delegates_to_session_service(
        self, activities, mock_session_service, mock_session_manager, identity,
    ):
        params = ScheduledSessionParams(
            schedule_id="sched-1",
            blueprint_id="bp-1",
            identity=identity,
            inputs={"user_prompt": "Generate report"},
            dedupe_key="dedup-1",
        )
        result = activities.provision_scheduled_session(params)
        assert result.session_id == "session-abc-123"
        mock_session_service.provision_scheduled_session.assert_called_once_with(
            identity=identity,
            blueprint_id="bp-1",
            inputs={"user_prompt": "Generate report"},
            schedule_id="sched-1",
            credential_user_id="",
            dedupe_key="dedup-1",
        )
        mock_session_manager.save_record.assert_called_once()
        assert result.params.execution_context.engine_handle == (
            "sched-session-session-abc-123"
        )

    def test_builds_provision_result_via_service(
        self, activities, mock_session_service, identity,
    ):
        params = ScheduledSessionParams(
            schedule_id="sched-1",
            blueprint_id="bp-1",
            identity=identity,
            dedupe_key="dedup-2",
        )
        result = activities.provision_scheduled_session(params)
        mock_session_service.build_scheduled_execution_params.assert_called_once_with(
            "session-abc-123",
            engine_name="temporal",
            engine_handle="sched-session-session-abc-123",
        )
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
    def test_delegates_to_record_outcome(self, activities, mock_schedule_service):
        params = RecordOutcomeParams(
            schedule_id="sched-1",
            session_id="session-1",
            outcome=RunOutcome.COMPLETED,
            started_at="2026-07-20T10:00:00+00:00",
        )
        activities.record_scheduled_outcome(params)
        mock_schedule_service.record_outcome.assert_called_once()
        call_args = mock_schedule_service.record_outcome.call_args[0]
        assert call_args[0] == "sched-1"
        assert call_args[1] == "session-1"
        assert call_args[2] == RunOutcome.COMPLETED

    def test_parses_started_at_from_iso(self, activities, mock_schedule_service):
        params = RecordOutcomeParams(
            schedule_id="sched-1",
            session_id="session-1",
            outcome=RunOutcome.COMPLETED,
            started_at="2026-07-20T10:30:00+00:00",
        )
        activities.record_scheduled_outcome(params)
        started = mock_schedule_service.record_outcome.call_args[0][3]
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
        started = mock_schedule_service.record_outcome.call_args[0][3]
        assert isinstance(started, datetime)
        assert (datetime.now(timezone.utc) - started).total_seconds() < 5
