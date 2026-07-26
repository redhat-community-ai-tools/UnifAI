from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from mas.core.tracing.models import ObservationHandle


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
