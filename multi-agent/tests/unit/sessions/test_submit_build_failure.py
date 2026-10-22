"""A build failure in submit() or on the Temporal worker ends with a FAILED session and a safe error."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from temporalio.exceptions import ApplicationError

from mas.elements.common.exceptions import PluginConfigurationError
from mas.engine.distributed.node_executor import NodeExecutor
from mas.session.domain.exceptions import SessionBuildError
from mas.session.domain.models import SessionMeta
from mas.session.domain.status import SessionStatus
from mas.session.execution.lifecycle import SessionLifecycle
from mas.session.execution.lifecycle_handler import BackgroundLifecycleHandler
from mas.session.service import SessionService
from mas.core.execution_context import ExecutionContext

SECRET = "sk-very-secret"


class FakeEngine:
    def __init__(self):
        self.submitted = []

    def generate_handle(self, session_id):
        return f"wf-{session_id}"

    def submit(self, session, request):
        self.submitted.append(session)


def _service(get_session):
    record = MagicMock()
    record.metadata = SessionMeta()
    record.status = SessionStatus.QUEUED
    record.run_context = ExecutionContext(engine_handle="wf-s-1")
    record.update_context = lambda **kw: setattr(record, "run_context", record.run_context.model_copy(update=kw))
    manager = MagicMock()
    manager.get_session.side_effect = get_session
    manager.get_record.return_value = record
    engine = FakeEngine()
    return SessionService(manager, MagicMock(), MagicMock(), background_engine=engine), manager, record, engine


def test_submit_build_error_marks_failed_and_rolls_back_the_handle():
    err = PluginConfigurationError("Invalid qdrant settings", {"api_key": SECRET})
    svc, manager, record, engine = _service(err)

    with pytest.raises(SessionBuildError) as exc:
        svc.submit("s-1", {"q": "hi"})

    assert record.status == SessionStatus.FAILED
    assert record.run_context.engine_handle is None
    assert record.metadata.error["type"] == "session_build_failed"
    assert SECRET not in record.metadata.error["message"] + str(exc.value)
    assert exc.value.__cause__ is err
    assert engine.submitted == []


def test_submit_normal_path_is_unchanged():
    session = SimpleNamespace(
        record=SimpleNamespace(metadata=SimpleNamespace(hitl_enabled=False)),
        run_context=ExecutionContext(),
    )
    svc, manager, record, engine = _service(lambda sid: session)

    assert svc.submit("s-1", {}) == "wf-s-1"
    assert engine.submitted == [session]
    assert record.status == SessionStatus.QUEUED


def test_error_message_is_length_limited():
    err = PluginConfigurationError("x" * 5000, {})
    svc, *_ = _service(err)
    with pytest.raises(SessionBuildError) as exc:
        svc.submit("s-1", {})
    assert len(exc.value.message) <= 200


# ── worker side ──────────────────────────────────────────────────────

def _executor(error):
    factory = MagicMock()
    factory.build_runtime_plan.side_effect = error
    return NodeExecutor(session_factory=factory, tracing_service=SimpleNamespace())


def test_worker_build_error_becomes_a_safe_session_build_error():
    err = PluginConfigurationError("Invalid tool", {"api_key": SECRET})
    bp = {"name": "mini", "description": "", "plan": [], "providers": [], "llms": [],
          "retrievers": [], "tools": [], "nodes": []}
    with pytest.raises(SessionBuildError) as exc:
        _executor(err)._execute_node_inner("n1", bp, None, MagicMock(), None,
                                            SimpleNamespace(session_id="s-1"))
    assert exc.value.session_id == "s-1"
    assert "n1" in exc.value.message and "Invalid tool" not in exc.value.message and SECRET not in exc.value.message


def test_activity_error_is_non_retryable_and_hides_the_cause():
    from inbound.temporal.activities.graph_node_activities import _as_non_retryable
    out = _as_non_retryable(SessionBuildError("s-1", "Session build failed (X): bad"))
    assert isinstance(out, ApplicationError)
    assert out.non_retryable and out.type == "session_build_failed"


def test_workflow_recognises_a_build_failure_in_the_cause_chain():
    from inbound.temporal.workflows.session_workflow import _find_build_failure
    app = ApplicationError("Session build failed (X): bad", type="session_build_failed", non_retryable=True)
    wrapper = RuntimeError("Activity task failed")
    wrapper.__cause__ = RuntimeError("Child workflow failed")
    wrapper.__cause__.__cause__ = app
    assert _find_build_failure(wrapper) == "Session build failed (X): bad"
    assert _find_build_failure(RuntimeError("other")) is None


def test_fail_session_records_the_build_error_in_metadata():
    record = MagicMock()
    record.metadata = SessionMeta()
    record.status = SessionStatus.RUNNING
    manager = MagicMock()
    manager.get_record.return_value = record
    handler = BackgroundLifecycleHandler(manager, SessionLifecycle(MagicMock()))

    handler.fail("s-1", "Session build failed (X): " + "m" * 900, "session_build_failed")

    assert record.status == SessionStatus.FAILED
    assert record.metadata.error["type"] == "session_build_failed"
    assert len(record.metadata.error["message"]) <= 200


def test_fail_session_without_error_type_is_unchanged():
    record = MagicMock()
    record.metadata = SessionMeta()
    record.status = SessionStatus.RUNNING
    manager = MagicMock()
    manager.get_record.return_value = record
    BackgroundLifecycleHandler(manager, SessionLifecycle(MagicMock())).fail("s-1", "boom")
    assert record.status == SessionStatus.FAILED
    assert getattr(record.metadata, "error", None) is None
