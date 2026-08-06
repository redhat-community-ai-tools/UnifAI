"""Shared Temporal workflow ID helpers."""


def scheduled_session_workflow_id(run_id: str) -> str:
    """Workflow ID for the SessionWorkflow child of a schedule tick."""
    return f"sched-session-{run_id}"
