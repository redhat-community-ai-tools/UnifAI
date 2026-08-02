"""Unit tests for Temporal DTO models.

Covers: ScheduledSessionParams, StageScheduledInputsParams,
        BuildSessionWorkflowParamsInput, RunOutcome, PostExecutionParams.
(Test Plan section 16.2)
"""
import pytest

from mas.core.identity import Identity
from mas.core.execution_context import ExecutionContext
from mas.engine.domain.models import GraphDefinition
from mas.graph.state.graph_state import GraphState
from mas.session.execution.ports import ScheduledExecutionParams
from temporal.models import (
    BuildSessionWorkflowParamsInput,
    GraphExecutionParams,
    PostExecutionParams,
    RunOutcome,
    ScheduledSessionParams,
    SessionWorkflowParams,
    StageScheduledInputsParams,
)


class TestScheduledSessionParams:
    def test_serialization_roundtrip(self):
        identity = Identity.user("user-1")
        params = ScheduledSessionParams(
            schedule_id="p1",
            blueprint_id="bp-1",
            identity=identity,
            text="hello",
            inputs={"k": "v"},
            source="shortcut_copy",
        )
        dumped = params.model_dump(mode="json")
        restored = ScheduledSessionParams(**dumped)
        assert restored.schedule_id == "p1"
        assert restored.identity.id == "user-1"
        assert restored.text == "hello"
        assert restored.inputs == {"k": "v"}
        assert restored.source == "shortcut_copy"


class TestStageScheduledInputsParams:
    def test_defaults(self):
        params = StageScheduledInputsParams(run_id="r1")
        assert params.inputs == {}
        assert params.text == ""

    def test_with_values(self):
        params = StageScheduledInputsParams(
            run_id="r1", inputs={"a": 1}, text="Go",
        )
        assert params.inputs == {"a": 1}
        assert params.text == "Go"


class TestBuildSessionWorkflowParamsInput:
    def test_minimal(self):
        params = BuildSessionWorkflowParamsInput(run_id="r1")
        assert params.run_id == "r1"


class TestRunOutcome:
    def test_completed_value(self):
        assert RunOutcome.COMPLETED == "COMPLETED"

    def test_failed_value(self):
        assert RunOutcome.FAILED == "FAILED"

    def test_cancelled_value(self):
        assert RunOutcome.CANCELLED == "CANCELLED"

    def test_enum_members(self):
        assert set(RunOutcome) == {
            RunOutcome.COMPLETED,
            RunOutcome.FAILED,
            RunOutcome.CANCELLED,
        }


class TestPostExecutionParams:
    def test_all_fields(self):
        params = PostExecutionParams(
            schedule_id="p1",
            run_id="r1",
            status=RunOutcome.FAILED,
            started_at="2026-07-20T10:00:00+00:00",
        )
        assert params.schedule_id == "p1"
        assert params.run_id == "r1"
        assert params.status == RunOutcome.FAILED
        assert params.started_at == "2026-07-20T10:00:00+00:00"

    def test_status_is_run_outcome_enum(self):
        params = PostExecutionParams(
            schedule_id="p1", run_id="r1",
            status=RunOutcome.COMPLETED, started_at="t",
        )
        assert isinstance(params.status, RunOutcome)


class TestSessionWorkflowParamsDomainMapping:
    def test_roundtrip_to_scheduled_execution_params(self):
        ctx = ExecutionContext(session_id="r1", engine_name="temporal")
        state = GraphState()
        definition = GraphDefinition()
        transport = SessionWorkflowParams(
            run_id="r1",
            execution_context=ctx,
            graph_execution_params=GraphExecutionParams(
                state=state,
                graph_definition=definition,
                session_id="r1",
                execution_context=ctx,
            ),
        )

        domain = transport.to_scheduled_execution_params()
        assert isinstance(domain, ScheduledExecutionParams)
        assert domain.run_id == "r1"
        assert domain.execution_context == ctx
        assert domain.graph_state is state
        assert domain.graph_definition is definition

        restored = SessionWorkflowParams.from_scheduled_execution_params(domain)
        assert restored.run_id == "r1"
        assert restored.execution_context == ctx
        assert restored.graph_execution_params.state is state
        assert restored.graph_execution_params.graph_definition is definition
        assert restored.graph_execution_params.session_id == "r1"
