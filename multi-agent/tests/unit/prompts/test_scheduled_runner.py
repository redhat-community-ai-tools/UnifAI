"""
Unit tests for ScheduledSessionRunner — verifies ordering, cancellation,
and failure handling without any infrastructure (Temporal, Mongo, etc.).
"""
import pytest

from mas.scheduling.models import RunOutcome
from mas.session.domain.exceptions import (
    ScheduledSessionCancelledException,
    ScheduledSessionSetupError,
)
from mas.session.execution.scheduled_runner import ScheduledSessionRunner


class FakeParams:
    """Stand-in for ScheduledExecutionParams in tests."""
    def __init__(self, run_id: str = "test-session"):
        self.run_id = run_id


class MockScheduledRunOps:
    """Configurable mock implementing ScheduledRunOps protocol."""

    def __init__(
        self,
        *,
        provision_result=None,
        provision_raises=None,
        execute_result=RunOutcome.COMPLETED,
        execute_raises=None,
        record_raises=None,
    ):
        self._provision_result = provision_result or ("sess-123", FakeParams())
        self._provision_raises = provision_raises
        self._execute_result = execute_result
        self._execute_raises = execute_raises
        self._record_raises = record_raises

        self.calls: list[str] = []
        self.recorded_session_id: str | None = None
        self.recorded_outcome: RunOutcome | None = None
        self.recorded_failure_reason: str | None = None

    async def provision(self):
        self.calls.append("provision")
        if self._provision_raises:
            raise self._provision_raises
        return self._provision_result

    async def execute(self, params):
        self.calls.append("execute")
        if self._execute_raises:
            raise self._execute_raises
        return self._execute_result

    async def record(self, session_id, outcome, failure_reason):
        self.calls.append("record")
        self.recorded_session_id = session_id
        self.recorded_outcome = outcome
        self.recorded_failure_reason = failure_reason
        if self._record_raises:
            raise self._record_raises


class TestScheduledSessionRunnerOrdering:
    """Verify the canonical ordering: provision → execute → record."""

    @pytest.mark.asyncio
    async def test_happy_path_ordering(self):
        ops = MockScheduledRunOps()
        runner = ScheduledSessionRunner()

        result = await runner.run(ops)

        assert result == "sess-123"
        assert ops.calls == ["provision", "execute", "record"]

    @pytest.mark.asyncio
    async def test_happy_path_records_completed(self):
        ops = MockScheduledRunOps(execute_result=RunOutcome.COMPLETED)
        runner = ScheduledSessionRunner()

        await runner.run(ops)

        assert ops.recorded_outcome == RunOutcome.COMPLETED
        assert ops.recorded_failure_reason is None

    @pytest.mark.asyncio
    async def test_execute_returns_failed(self):
        ops = MockScheduledRunOps(execute_result=RunOutcome.FAILED)
        runner = ScheduledSessionRunner()

        result = await runner.run(ops)

        assert result == "sess-123"
        assert ops.recorded_outcome == RunOutcome.FAILED
        assert ops.recorded_failure_reason is None


class TestScheduledSessionRunnerFailure:
    """Verify failure handling."""

    @pytest.mark.asyncio
    async def test_execute_raises_records_failed(self):
        ops = MockScheduledRunOps(execute_raises=RuntimeError("LLM timeout"))
        runner = ScheduledSessionRunner()

        result = await runner.run(ops)

        assert result == "sess-123"
        assert ops.calls == ["provision", "execute", "record"]
        assert ops.recorded_outcome == RunOutcome.FAILED
        assert "RuntimeError" in ops.recorded_failure_reason
        assert "LLM timeout" in ops.recorded_failure_reason

    @pytest.mark.asyncio
    async def test_provision_raises_no_record(self):
        ops = MockScheduledRunOps(provision_raises=ValueError("blueprint deleted"))
        runner = ScheduledSessionRunner()

        with pytest.raises(ScheduledSessionSetupError) as exc_info:
            await runner.run(ops)

        assert ops.calls == ["provision"]
        assert "ValueError" in str(exc_info.value)
        assert ops.recorded_session_id is None

    @pytest.mark.asyncio
    async def test_provision_raises_setup_error_contains_reason(self):
        ops = MockScheduledRunOps(provision_raises=KeyError("not found"))
        runner = ScheduledSessionRunner()

        with pytest.raises(ScheduledSessionSetupError) as exc_info:
            await runner.run(ops)

        assert exc_info.value.reason is not None
        assert "KeyError" in exc_info.value.reason


class TestScheduledSessionRunnerCancellation:
    """Verify cancellation handling."""

    @pytest.mark.asyncio
    async def test_cancellation_records_then_reraises(self):
        ops = MockScheduledRunOps(
            execute_raises=ScheduledSessionCancelledException()
        )
        runner = ScheduledSessionRunner()

        with pytest.raises(ScheduledSessionCancelledException):
            await runner.run(ops)

        assert ops.calls == ["provision", "execute", "record"]
        assert ops.recorded_outcome == RunOutcome.CANCELLED
        assert ops.recorded_failure_reason == "WorkflowCancelled"

    @pytest.mark.asyncio
    async def test_cancellation_still_calls_record(self):
        ops = MockScheduledRunOps(
            execute_raises=ScheduledSessionCancelledException()
        )
        runner = ScheduledSessionRunner()

        with pytest.raises(ScheduledSessionCancelledException):
            await runner.run(ops)

        assert "record" in ops.calls


class TestScheduledSessionRunnerRecordGuard:
    """Verify record() is only called when session_id is available."""

    @pytest.mark.asyncio
    async def test_no_record_when_no_session_id(self):
        ops = MockScheduledRunOps(provision_raises=RuntimeError("boom"))
        runner = ScheduledSessionRunner()

        with pytest.raises(ScheduledSessionSetupError):
            await runner.run(ops)

        assert "record" not in ops.calls
