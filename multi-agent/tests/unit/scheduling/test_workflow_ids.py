"""Unit tests for shared Temporal workflow ID helpers."""
from temporal.workflow_ids import scheduled_session_workflow_id


def test_scheduled_session_workflow_id():
    assert scheduled_session_workflow_id("run-abc") == "sched-session-run-abc"
