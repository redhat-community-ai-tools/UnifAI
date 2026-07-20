from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from mas.core.tracing.models import ObservationHandle


def _noop_update(**kwargs: Any) -> None:
    pass


_NOOP_HANDLE = ObservationHandle(_update_fn=_noop_update)


class NoOpTracingService:
    """Zero-overhead stand-in when tracing is not configured."""

    enabled: bool = False

    @contextmanager
    def trace_session(
        self,
        session_id: str,
        user_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]:
        yield _NOOP_HANDLE

    @contextmanager
    def trace_node(
        self,
        node_uid: str,
        node_type: str,
        display_name: str = "",
    ) -> Iterator[ObservationHandle]:
        yield _NOOP_HANDLE

    @contextmanager
    def trace_llm(
        self,
        model: str,
        provider: str,
        input_messages: Optional[List[Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]:
        yield _NOOP_HANDLE

    @contextmanager
    def trace_tool(
        self,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]:
        yield _NOOP_HANDLE

    @contextmanager
    def trace_agent_iteration(
        self,
        iteration: int,
        strategy: str = "",
    ) -> Iterator[ObservationHandle]:
        yield _NOOP_HANDLE

    def flush(self) -> None:
        pass
