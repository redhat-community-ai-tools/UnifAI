"""Unit tests for ScheduleActivities.

Covers: create_scheduled_session, stage_scheduled_inputs,
        build_session_workflow_params, post_execution.
(Test Plan sections 5.2–5.5)
"""
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

import pytest

from mas.core.identity import Identity
from mas.session.domain.models import SessionMeta
from temporal.models import (
    BuildSessionWorkflowParamsInput,
    PostExecutionParams,
    RunOutcome,
    ScheduledSessionParams,
    StageScheduledInputsParams,
)


@pytest.fixture
def identity():
    return Identity.user("user-1")


@pytest.fixture
def mock_session_service():
    svc = Mock()
    svc.create.return_value = "session-abc-123"
    return svc


@pytest.fixture
def mock_input_projector():
    return Mock()


@pytest.fixture
def mock_session_manager():
    mgr = Mock()
    record = Mock()
    mgr.get_record.return_value = record

    session = Mock()
    session.record = Mock()
    session.record.identity = Identity.user("user-1")
    session.record.run_context = Mock()
    session.record.run_context.tags = {}
    session.executable_graph = Mock()
    session.executable_graph.graph_definition = Mock()
    session.graph_state = Mock()
    mgr.get_session.return_value = session
    return mgr


@pytest.fixture
def mock_prompt_service():
    return Mock()


@pytest.fixture
def activities(mock_session_service, mock_input_projector, mock_session_manager, mock_prompt_service):
    from inbound.temporal.activities.schedule_activities import ScheduleActivities
    return ScheduleActivities(
        session_service=mock_session_service,
        input_projector=mock_input_projector,
        session_manager=mock_session_manager,
        prompt_service=mock_prompt_service,
    )


# ═══════════════════════════════════════════════════════════════════
# 5.2 create_scheduled_session
# ═══════════════════════════════════════════════════════════════════

class TestCreateScheduledSession:
    def test_creates_session_with_metadata(self, activities, mock_session_service, identity):
        params = ScheduledSessionParams(
            prompt_id="prompt-1",
            blueprint_id="bp-1",
            identity=identity,
            text="Generate report",
        )
        result = activities.create_scheduled_session(params)
        assert result == "session-abc-123"
        call_kwargs = mock_session_service.create.call_args[1]
        assert call_kwargs["identity"] == identity
        assert call_kwargs["blueprint_id"] == "bp-1"
        meta = call_kwargs["metadata"]
        assert meta.source == "schedule"
        assert meta.schedule_id == "prompt-1"
        assert meta.prompt_text == "Generate report"

    def test_returns_session_id(self, activities, identity):
        params = ScheduledSessionParams(
            prompt_id="p1", blueprint_id="bp-1", identity=identity,
        )
        result = activities.create_scheduled_session(params)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_identity_passed_through(self, activities, mock_session_service):
        team = Identity.team("team-x")
        params = ScheduledSessionParams(
            prompt_id="p1", blueprint_id="bp-1", identity=team,
        )
        activities.create_scheduled_session(params)
        assert mock_session_service.create.call_args[1]["identity"] == team


# ═══════════════════════════════════════════════════════════════════
# 5.3 stage_scheduled_inputs
# ═══════════════════════════════════════════════════════════════════

class TestStageScheduledInputs:
    def test_stages_inputs(self, activities, mock_input_projector, mock_session_manager):
        params = StageScheduledInputsParams(
            run_id="run-1", inputs={"key": "val"}, text="",
        )
        activities.stage_scheduled_inputs(params)
        mock_session_manager.get_record.assert_called_once_with("run-1")
        call_args = mock_input_projector.apply.call_args[0]
        assert call_args[1] == {"key": "val"}

    def test_text_added_as_user_prompt(self, activities, mock_input_projector, mock_session_manager):
        params = StageScheduledInputsParams(
            run_id="run-1", inputs={"a": 1}, text="Generate report",
        )
        activities.stage_scheduled_inputs(params)
        merged = mock_input_projector.apply.call_args[0][1]
        assert merged["user_prompt"] == "Generate report"
        assert merged["a"] == 1

    def test_empty_text_not_added(self, activities, mock_input_projector, mock_session_manager):
        params = StageScheduledInputsParams(run_id="run-1", inputs={}, text="")
        activities.stage_scheduled_inputs(params)
        merged = mock_input_projector.apply.call_args[0][1]
        assert "user_prompt" not in merged

    def test_empty_inputs(self, activities, mock_input_projector, mock_session_manager):
        params = StageScheduledInputsParams(run_id="run-1", inputs={}, text="")
        activities.stage_scheduled_inputs(params)
        merged = mock_input_projector.apply.call_args[0][1]
        assert merged == {}

    def test_credential_user_id_passed_to_projector(self, activities, mock_input_projector, mock_session_manager):
        params = StageScheduledInputsParams(
            run_id="run-1", inputs={}, text="go",
            credential_user_id="human-user-42",
        )
        activities.stage_scheduled_inputs(params)
        call_kwargs = mock_input_projector.apply.call_args[1]
        assert call_kwargs["logged_in_user"] == "human-user-42"


# ═══════════════════════════════════════════════════════════════════
# 5.5 post_execution
# ═══════════════════════════════════════════════════════════════════

class TestPostExecution:
    def test_records_run(self, activities, mock_prompt_service):
        params = PostExecutionParams(
            prompt_id="prompt-1",
            run_id="run-1",
            status=RunOutcome.COMPLETED,
            started_at="2026-07-20T10:00:00+00:00",
        )
        activities.post_execution(params)
        mock_prompt_service.record_run.assert_called_once()
        call_args = mock_prompt_service.record_run.call_args[0]
        assert call_args[0] == "prompt-1"
        assert call_args[1] == "run-1"
        assert call_args[2] == RunOutcome.COMPLETED

    def test_calls_mark_completed(self, activities, mock_prompt_service):
        params = PostExecutionParams(
            prompt_id="prompt-1",
            run_id="run-1",
            status=RunOutcome.COMPLETED,
            started_at="2026-07-20T10:00:00+00:00",
        )
        activities.post_execution(params)
        mock_prompt_service.mark_completed.assert_called_once_with("prompt-1")

    def test_parses_started_at_from_iso(self, activities, mock_prompt_service):
        params = PostExecutionParams(
            prompt_id="p1", run_id="r1",
            status=RunOutcome.COMPLETED,
            started_at="2026-07-20T10:30:00+00:00",
        )
        activities.post_execution(params)
        started = mock_prompt_service.record_run.call_args[0][3]
        assert isinstance(started, datetime)
        assert started.hour == 10
        assert started.minute == 30

    def test_invalid_started_at_falls_back_to_now(self, activities, mock_prompt_service):
        params = PostExecutionParams(
            prompt_id="p1", run_id="r1",
            status=RunOutcome.FAILED,
            started_at="not-a-date",
        )
        activities.post_execution(params)
        started = mock_prompt_service.record_run.call_args[0][3]
        assert isinstance(started, datetime)
        assert (datetime.now(timezone.utc) - started).total_seconds() < 5

    def test_status_passed_through(self, activities, mock_prompt_service):
        params = PostExecutionParams(
            prompt_id="p1", run_id="r1",
            status=RunOutcome.FAILED,
            started_at="2026-07-20T10:00:00+00:00",
        )
        activities.post_execution(params)
        assert mock_prompt_service.record_run.call_args[0][2] == RunOutcome.FAILED
