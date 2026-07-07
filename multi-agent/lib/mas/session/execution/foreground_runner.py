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
"""
import logging
import threading
from typing import Any, Iterator, Union

from mas.core.channels import ChannelFactory
from mas.core.enums import ResourceCategory
from mas.graph.state.graph_state import GraphState
from mas.session.execution.lifecycle import SessionLifecycle
from mas.session.domain.workflow_session import WorkflowSession

logger = logging.getLogger(__name__)


class ForegroundSessionRunner:
    """
    Orchestrates synchronous graph execution with session lifecycle hooks.

    Delegates lifecycle transitions (begin / complete / fail) to
    SessionLifecycle.  When streaming, a channel writer+reader pair
    decouples execution from event delivery.
    """

    def __init__(
        self,
        lifecycle: SessionLifecycle,
        channel_factory: ChannelFactory,
    ) -> None:
        self._lifecycle = lifecycle
        self._channel_factory = channel_factory

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

        try:
            final_state = session.executable_graph.run(
                session.graph_state, session_id=session.get_run_id(),
            )
        except Exception as e:
            self._lifecycle.fail(session.record, e)
            raise

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

        channel = self._channel_factory.create(session.get_run_id())
        reader = self._channel_factory.create_reader(session.get_run_id())
        self._inject_channel(session, channel)

        result: dict = {"state": None, "error": None}

        def _execute() -> None:
            try:
                result["state"] = session.executable_graph.run(
                    session.graph_state, session_id=session.get_run_id(),
                )
            except Exception as e:
                result["error"] = e
            finally:
                channel.close()

        thread = threading.Thread(target=_execute, name=f"graph-exec-{session.get_run_id()[:8]}")
        thread.start()

        try:
            yield from reader
        finally:
            channel.close()
            thread.join(timeout=60)
            self._inject_channel(session, None)

            try:
                if result["error"]:
                    self._lifecycle.fail(session.record, result["error"])
                elif result["state"] is not None:
                    self._lifecycle.complete(session.record, result["state"])
            except Exception:
                logger.exception("Failed to complete session lifecycle")

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _inject_channel(session: WorkflowSession, channel) -> None:
        for node in session.session_registry.all_of(ResourceCategory.NODE).values():
            if hasattr(node, "set_streaming_channel"):
                node.set_streaming_channel(channel)
