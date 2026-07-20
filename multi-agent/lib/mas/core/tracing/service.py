from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Protocol, runtime_checkable

from mas.core.tracing.models import ObservationHandle


@runtime_checkable
class TracingService(Protocol):
    """Domain-level tracing port.

    All observability instrumentation depends on this protocol,
    never on a concrete SDK.  When tracing is disabled the
    composition root injects NoOpTracingService.
    """

    @property
    def enabled(self) -> bool: ...

    @contextmanager
    def trace_session(
        self,
        session_id: str,
        user_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]: ...

    @contextmanager
    def trace_node(
        self,
        node_uid: str,
        node_type: str,
        display_name: str = "",
    ) -> Iterator[ObservationHandle]: ...

    @contextmanager
    def trace_llm(
        self,
        model: str,
        provider: str,
        input_messages: Optional[List[Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]: ...

    @contextmanager
    def trace_tool(
        self,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]: ...

    @contextmanager
    def trace_agent_iteration(
        self,
        iteration: int,
        strategy: str = "",
    ) -> Iterator[ObservationHandle]: ...

    def flush(self) -> None: ...
