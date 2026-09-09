"""
Foreground (in-process) session execution with lifecycle orchestration.

Single ``run()`` entry point with an optional ``stream`` flag:
  - stream=False → blocking execution, returns final GraphState.
  - stream=True  → graph runs on a background thread; events flow
                    through the channel layer and are yielded to the caller.

Streaming is an orthogonal concern handled entirely by the channel:
nodes emit events via SessionChannel, the caller reads them via
SessionChannelReader.  The executor only ever calls ``run()`` — there
is no ``stream()`` on the executor.

Runtime capabilities (streaming channel, HITL gate/policy) are
injected into nodes via ``NodeRuntimeBinder`` which uses capability
protocols instead of ``hasattr`` duck-typing.
"""
import logging
import threading
from typing import Any, Iterator, Optional, Union

from mas.core.channels import ChannelFactory
from mas.core.hitl.models import ToolApprovalPolicy
from mas.core.hitl.ports import ApprovalGate, ApprovalGateFactory
from mas.core.runtime_binder import NodeRuntimeBinder, NodeRuntimeBindings
from mas.core.tracing import TracingService
from mas.graph.state.graph_state import GraphState
from mas.session.execution.lifecycle import SessionLifecycle
from mas.session.domain.workflow_session import WorkflowSession

logger = logging.getLogger(__name__)


class ForegroundSessionRunner:
    """
    Orchestrates synchronous graph execution with session lifecycle hooks.

    Delegates lifecycle transitions (begin / complete / fail) to
    SessionLifecycle.  When streaming, a channel writer+reader pair
    decouples execution from event delivery.  Runtime capability
    injection is delegated to ``NodeRuntimeBinder``.

    HITL gate construction is delegated to ``ApprovalGateFactory``
    (port) so this class never imports adapter implementations.
    """

    def __init__(
        self,
        lifecycle: SessionLifecycle,
        channel_factory: ChannelFactory,
        gate_factory: Optional[ApprovalGateFactory] = None,
        binder: Optional[NodeRuntimeBinder] = None,
        tracing_service: TracingService = None,
    ) -> None:
        self._lifecycle = lifecycle
        self._channel_factory = channel_factory
        self._gate_factory = gate_factory
        self._binder = binder or NodeRuntimeBinder.default()
        self._tracing = tracing_service

    def run(
        self,
        session: WorkflowSession,
        scope: str = "public",
        stream: bool = False,
    ) -> Union[GraphState, Iterator[Any]]:
        """
        Execute the session graph.

        Args:
            session: Fully hydrated workflow session.
            scope: Visibility scope for this execution.
            stream: If True, returns an event iterator instead of the
                    final state.  The lifecycle is completed internally
                    once execution finishes.

        Returns:
            ``GraphState`` when *stream* is False;
            ``Iterator[Any]`` of channel events when *stream* is True.
        """
        from global_utils.utils.logging_config import set_session_id
        run_id = session.get_run_id() if hasattr(session, "get_run_id") else None
        if run_id:
            set_session_id(run_id)
        if stream:
            return self._run_streaming(session, scope)
        return self._run_blocking(session, scope)

    # ── Blocking path ────────────────────────────────────────────

    def _run_blocking(
        self,
        session: WorkflowSession,
        scope: str,
    ) -> GraphState:
        self._lifecycle.begin(session.record, scope)
        session.execution_holder.context = session.record.run_context

        run_id = session.get_run_id()
        user_id = getattr(session.record.run_context, "identity_id", "") or ""

        with self._tracing.trace_session(
            session_id=run_id,
            user_id=user_id,
            metadata={"scope": scope},
        ):
            try:
                final_state = session.executable_graph.run(
                    session.graph_state, session_id=run_id,
                )
            except Exception as e:
                self._lifecycle.fail(session.record, e)
                raise
            finally:
                self._tracing.flush()

        self._lifecycle.complete(session.record, final_state)
        return final_state

    # ── Streaming path ───────────────────────────────────────────

    def _run_streaming(
        self,
        session: WorkflowSession,
        scope: str,
    ) -> Iterator[Any]:
        self._lifecycle.begin(session.record, scope)
        session.execution_holder.context = session.record.run_context

        run_id = session.get_run_id()

        channel = self._channel_factory.create_input_capable(run_id)
        if channel is None:
            channel = self._channel_factory.create(run_id)

        reader = self._channel_factory.create_reader(run_id)

        gate, policy = self._build_hitl(channel, session, run_id)

        bindings = NodeRuntimeBindings(
            channel=channel,
            approval_gate=gate,
            approval_policy=policy,
        )
        self._binder.bind_all(session.session_registry, bindings)

        result: dict = {"state": None, "error": None}
        tracing = self._tracing
        user_id = getattr(session.record.run_context, "identity_id", "") or ""

        def _execute() -> None:
            with tracing.trace_session(
                session_id=run_id,
                user_id=user_id,
                metadata={"scope": scope, "streaming": True},
            ):
                try:
                    result["state"] = session.executable_graph.run(
                        session.graph_state, session_id=run_id,
                    )
                except Exception as e:
                    result["error"] = e
                finally:
                    tracing.flush()
                    channel.close()

        thread = threading.Thread(target=_execute, name=f"graph-exec-{run_id[:8]}")
        thread.start()

        try:
            yield from reader
        finally:
            channel.close()
            thread.join(timeout=60)
            self._binder.unbind_all(session.session_registry)

            if self._gate_factory is not None:
                self._gate_factory.remove(run_id)

            try:
                if result["error"]:
                    self._lifecycle.fail(session.record, result["error"])
                elif result["state"] is not None:
                    self._lifecycle.complete(session.record, result["state"])
            except Exception:
                logger.exception("Failed to complete session lifecycle")

    # ── HITL wiring ──────────────────────────────────────────────

    def _build_hitl(
        self,
        channel: Any,
        session: WorkflowSession,
        run_id: str,
    ) -> tuple[Optional[ApprovalGate], Optional[ToolApprovalPolicy]]:
        """Delegate gate + policy construction to the injected factory.

        Returns ``(None, None)`` when no factory was provided or the
        channel does not support input.
        """
        if self._gate_factory is None:
            return None, None
        return self._gate_factory.create(channel, session.record.metadata, run_id)
