from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import (
    Any,
    Callable,
    ContextManager,
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
)

from mas.core.tracing.models import ObservationHandle
from mas.core.tracing.service import TracingService


class CompositeTracingService(TracingService):
    """Fan every observation out to several tracing services.

    ``context_owner`` is the service whose spans carry the distributed
    trace context (e.g. OpenTelemetry, whose ``traceparent`` is injected on
    outbound HTTP calls).  It is entered *outermost* for sessions, so it
    sees the caller's ambient context (an inbound request or a Temporal
    activity span) before any other backend opens its own root, and
    *innermost* for every other scope, so its span is the current one
    while the traced code runs.  The other services (``others``) keep
    their own nesting between those two points.
    """

    def __init__(self, context_owner: TracingService, others: Sequence[TracingService]) -> None:
        self._owner = context_owner
        self._others = list(others)

    @property
    def enabled(self) -> bool:
        return self._owner.enabled or any(s.enabled for s in self._others)

    @property
    def delegates(self) -> List[TracingService]:
        return [self._owner, *self._others]

    @staticmethod
    def _combined_handle(handles: List[ObservationHandle]) -> ObservationHandle:
        def _update(**kwargs: Any) -> None:
            for h in handles:
                h.update(**kwargs)

        return ObservationHandle(_update_fn=_update)

    @contextmanager
    def _fan_out(
        self,
        open_cm: Callable[[TracingService], ContextManager[ObservationHandle]],
        *,
        owner_first: bool,
    ) -> Iterator[ObservationHandle]:
        order = [self._owner, *self._others] if owner_first else [*self._others, self._owner]
        with ExitStack() as stack:
            handles = [stack.enter_context(open_cm(s)) for s in order]
            yield self._combined_handle(handles)

    @contextmanager
    def trace_session(
        self,
        session_id: str,
        user_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]:
        with self._fan_out(
            lambda s: s.trace_session(session_id, user_id=user_id, metadata=metadata),
            owner_first=True,
        ) as handle:
            yield handle

    @contextmanager
    def trace_node(
        self,
        node_uid: str,
        node_type: str,
        display_name: str = "",
    ) -> Iterator[ObservationHandle]:
        with self._fan_out(
            lambda s: s.trace_node(node_uid, node_type, display_name=display_name),
            owner_first=False,
        ) as handle:
            yield handle

    @contextmanager
    def trace_llm(
        self,
        model: str,
        provider: str,
        input_messages: Optional[List[Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]:
        with self._fan_out(
            lambda s: s.trace_llm(
                model, provider, input_messages=input_messages, metadata=metadata,
            ),
            owner_first=False,
        ) as handle:
            yield handle

    @contextmanager
    def trace_tool(
        self,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]:
        with self._fan_out(
            lambda s: s.trace_tool(tool_name, tool_input=tool_input),
            owner_first=False,
        ) as handle:
            yield handle

    @contextmanager
    def trace_agent_iteration(
        self,
        iteration: int,
        strategy: str = "",
    ) -> Iterator[ObservationHandle]:
        with self._fan_out(
            lambda s: s.trace_agent_iteration(iteration, strategy=strategy),
            owner_first=False,
        ) as handle:
            yield handle

    def flush(self) -> None:
        for s in self.delegates:
            s.flush()

    def bind_to_current_context(self, fn):
        for s in self.delegates:
            fn = s.bind_to_current_context(fn)
        return fn

    def get_session_cost(self, session_id: str) -> Optional[float]:
        for s in self.delegates:
            cost = s.get_session_cost(session_id)
            if cost is not None:
                return cost
        return None
