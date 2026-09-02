"""
Temporal activity wrapper for session lifecycle transitions.

Pure one-liner delegates to the domain-level BackgroundLifecycleHandler.
"""
from temporalio import activity

from mas.graph.state.graph_state import GraphState
from mas.session.execution.lifecycle_handler import BackgroundLifecycleHandler
from temporal.models import (
    BeginSessionParams,
    CompleteSessionParams,
    FailSessionParams,
    CancelSessionParams,
)


class SessionLifecycleActivities:
    """Pure one-liner delegates to BackgroundLifecycleHandler."""

    def __init__(self, handler: BackgroundLifecycleHandler) -> None:
        self._handler = handler

    @activity.defn(name="begin_session")
    def begin_session(self, params: BeginSessionParams) -> GraphState:
        from global_utils.utils.logging_config import bind_correlation_ids
        bind_correlation_ids(params.request_id, params.run_id)
        return self._handler.begin(
            params.run_id, params.execution_context,
        )

    @activity.defn(name="complete_session")
    def complete_session(self, params: CompleteSessionParams) -> None:
        from global_utils.utils.logging_config import bind_correlation_ids
        bind_correlation_ids(session_id=params.run_id)
        self._handler.complete(params.run_id, params.final_state)

    @activity.defn(name="fail_session")
    def fail_session(self, params: FailSessionParams) -> None:
        from global_utils.utils.logging_config import bind_correlation_ids
        bind_correlation_ids(session_id=params.run_id)
        self._handler.fail(params.run_id, params.error_message)

    @activity.defn(name="cancel_session")
    def cancel_session(self, params: CancelSessionParams) -> None:
        from global_utils.utils.logging_config import bind_correlation_ids
        bind_correlation_ids(session_id=params.run_id)
        self._handler.cancel(params.run_id)
