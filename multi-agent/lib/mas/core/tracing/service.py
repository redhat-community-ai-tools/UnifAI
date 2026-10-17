from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, List, Optional, TypeVar

from mas.core.tracing.models import ObservationHandle

F = TypeVar("F", bound=Callable[..., Any])


class TracingService(ABC):
    """Domain-level tracing port.

    All observability instrumentation depends on this abstract class,
    never on a concrete SDK.  When tracing is disabled the
    composition root injects NoOpTracingService.
    """

    @property
    @abstractmethod
    def enabled(self) -> bool: ...

    @contextmanager
    @abstractmethod
    def trace_session(
        self,
        session_id: str,
        user_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]: ...

    @contextmanager
    @abstractmethod
    def trace_node(
        self,
        node_uid: str,
        node_type: str,
        display_name: str = "",
    ) -> Iterator[ObservationHandle]: ...

    @contextmanager
    @abstractmethod
    def trace_llm(
        self,
        model: str,
        provider: str,
        input_messages: Optional[List[Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]: ...

    @contextmanager
    @abstractmethod
    def trace_tool(
        self,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]: ...

    @contextmanager
    @abstractmethod
    def trace_agent_iteration(
        self,
        iteration: int,
        strategy: str = "",
    ) -> Iterator[ObservationHandle]: ...

    @abstractmethod
    def flush(self) -> None: ...

    def bind_to_current_context(self, fn: F) -> F:
        """Return ``fn`` bound to the caller's trace context.

        Use it for work handed to another thread, so spans opened there
        nest under the caller's current span.  The default is the
        identity; backends with thread-local context override it.
        """
        return fn

    def get_session_cost(self, session_id: str) -> Optional[float]:
        """Fetch the total USD cost for a session from the tracing backend.

        Returns a float (>= 0) when the session exists in the tracing
        backend, or None when it does not.  Non-abstract so existing
        subclasses aren't forced to implement it.
        """
        return None
