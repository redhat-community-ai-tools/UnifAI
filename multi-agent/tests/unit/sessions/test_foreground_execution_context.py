"""The foreground runner must ship the session's execution context to its executor.

Distributed (Temporal) workers rebuild elements with an empty context holder;
without the context in GraphExecutionParams they run as an anonymous identity
with no session id, which breaks per-user credentials.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from mas.core.execution_context import ExecutionContext
from mas.core.identity import resolve_identity
from mas.graph.state.graph_state import GraphState
from mas.session.execution.foreground_runner import ForegroundSessionRunner


def _ctx() -> ExecutionContext:
    return ExecutionContext(session_id="s-42", identity=resolve_identity("alice", "user"))


def test_blocking_run_passes_execution_context_to_executor():
    ctx = _ctx()
    session = MagicMock()
    session.record.run_context = ctx
    session.get_run_id.return_value = "s-42"
    session.executable_graph.run.return_value = GraphState()
    tracing = MagicMock()
    tracing.trace_session.return_value.__enter__ = MagicMock(return_value=None)
    tracing.trace_session.return_value.__exit__ = MagicMock(return_value=False)

    runner = ForegroundSessionRunner(lifecycle=MagicMock(), channel_factory=MagicMock(), tracing_service=tracing)
    runner._run_blocking(session, "public")

    kwargs = session.executable_graph.run.call_args.kwargs
    assert kwargs["execution_context"] is ctx
    assert kwargs["session_id"] == "s-42"


def test_temporal_executor_puts_execution_context_in_workflow_params():
    from outbound.temporal.executor import TemporalGraphExecutor
    from mas.engine.domain.models import GraphDefinition

    client = MagicMock()
    client.execute_workflow = AsyncMock(return_value=GraphState())
    cfg = MagicMock(temporal_task_queue="q")
    with patch("outbound.temporal.executor.get_temporal_client", AsyncMock(return_value=client)), \
         patch("outbound.temporal.executor.AppConfig.get_instance", return_value=cfg):
        asyncio.run(TemporalGraphExecutor(GraphDefinition())._execute(
            GraphState(), session_id="s-42", execution_context=_ctx(),
        ))

    params = client.execute_workflow.call_args.args[1]
    assert params.execution_context.session_id == "s-42"
    assert params.execution_context.credential_user_id() == "alice"
