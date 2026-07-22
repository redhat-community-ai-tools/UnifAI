"""Langfuse adapter implementing the TracingService protocol.

This is the only module that imports ``langfuse``.  All other code
depends on the domain-level ``TracingService`` protocol.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from langfuse import Langfuse, get_client, propagate_attributes

from mas.core.tracing.models import ObservationHandle

logger = logging.getLogger(__name__)


class LangfuseTracingService:
    """Production tracing service backed by the Langfuse Python SDK v4."""

    enabled: bool = True

    def __init__(
        self,
        *,
        secret_key: str = "",
        public_key: str = "",
        base_url: str = "https://us.cloud.langfuse.com",
    ) -> None:
        if secret_key and public_key:
            self._client = Langfuse(
                secret_key=secret_key,
                public_key=public_key,
                host=base_url,
            )
        else:
            self._client = get_client()

        if self._client.auth_check():
            logger.info("Langfuse tracing enabled (host=%s)", base_url)
        else:
            logger.warning("Langfuse auth check failed — traces may not be delivered")

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _make_handle(observation: Any) -> ObservationHandle:
        def _update(
            *,
            output: Any = None,
            usage_details: Optional[Dict[str, Any]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            level: Optional[str] = None,
            status_message: Optional[str] = None,
        ) -> None:
            kwargs: Dict[str, Any] = {}
            if output is not None:
                kwargs["output"] = output
            if usage_details is not None:
                kwargs["usage_details"] = usage_details
            if metadata is not None:
                kwargs["metadata"] = metadata
            if level is not None:
                kwargs["level"] = level
            if status_message is not None:
                kwargs["status_message"] = status_message
            if kwargs:
                observation.update(**kwargs)

        return ObservationHandle(_update_fn=_update)

    # ── session trace ────────────────────────────────────────────

    @contextmanager
    def trace_session(
        self,
        session_id: str,
        user_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]:
        trace_id = self._client.create_trace_id(seed=session_id)

        with self._client.start_as_current_observation(
            as_type="span",
            name=f"session:{session_id}",
            input=metadata,
            trace_context={"trace_id": trace_id},
        ) as obs:
            with propagate_attributes(
                session_id=session_id,
                user_id=user_id or None,
                metadata=metadata,
                trace_name=f"session:{session_id}",
            ):
                yield self._make_handle(obs)

    # ── node span ────────────────────────────────────────────────

    @contextmanager
    def trace_node(
        self,
        node_uid: str,
        node_type: str,
        display_name: str = "",
    ) -> Iterator[ObservationHandle]:
        with self._client.start_as_current_observation(
            as_type="span",
            name=display_name or node_uid,
            metadata={
                "node_uid": node_uid,
                "node_type": node_type,
            },
        ) as obs:
            yield self._make_handle(obs)

    # ── LLM generation ───────────────────────────────────────────

    @contextmanager
    def trace_llm(
        self,
        model: str,
        provider: str,
        input_messages: Optional[List[Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]:
        obs_metadata = {"provider": provider}
        if metadata:
            obs_metadata.update(metadata)

        with self._client.start_as_current_observation(
            as_type="generation",
            name=f"{provider}/{model}",
            model=model,
            input=input_messages,
            metadata=obs_metadata,
        ) as obs:
            yield self._make_handle(obs)

    # ── tool span ────────────────────────────────────────────────

    @contextmanager
    def trace_tool(
        self,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]:
        with self._client.start_as_current_observation(
            as_type="span",
            name=f"tool:{tool_name}",
            input=tool_input,
            metadata={"tool_name": tool_name},
        ) as obs:
            yield self._make_handle(obs)

    # ── agent iteration span ─────────────────────────────────────

    @contextmanager
    def trace_agent_iteration(
        self,
        iteration: int,
        strategy: str = "",
    ) -> Iterator[ObservationHandle]:
        with self._client.start_as_current_observation(
            as_type="span",
            name=f"iteration:{iteration}",
            metadata={
                "iteration": iteration,
                "strategy": strategy,
            },
        ) as obs:
            yield self._make_handle(obs)

    # ── flush ────────────────────────────────────────────────────

    def flush(self) -> None:
        self._client.flush()
