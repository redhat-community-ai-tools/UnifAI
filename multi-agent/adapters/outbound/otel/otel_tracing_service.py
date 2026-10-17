"""OpenTelemetry adapter implementing the TracingService port.

This is the only MAS module that imports ``opentelemetry`` for domain
spans.  Spans form the tree ``mas.session -> mas.node -> mas.agent.iteration
-> chat {model} / execute_tool {tool}``; model calls carry the GenAI
semantic-convention attributes (``gen_ai.*``).

Content is never recorded: prompts, completions, tool arguments and tool
results passed to the port are ignored, only their metadata (model,
provider, token counts, outcome) becomes span attributes or metrics.

Parenting uses a private span stack, not only the ambient OpenTelemetry
context, so the tree stays correct when another OTel-based backend
(Langfuse) opens its own spans in between.  ``attach_scopes`` selects the
scopes whose span also becomes the *current* span while the traced code
runs, which is what makes the HTTP instrumentations inject that span's
``traceparent`` on outbound calls.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Iterator, List, Optional, Tuple

from mas.core.tracing.models import ObservationHandle
from mas.core.tracing.service import TracingService
from opentelemetry import context as otel_context
from opentelemetry import metrics, trace
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

logger = logging.getLogger(__name__)

INSTRUMENTATION_NAME = "mas"

SCOPE_SESSION = "session"
SCOPE_NODE = "node"
SCOPE_ITERATION = "iteration"
SCOPE_LLM = "llm"
SCOPE_TOOL = "tool"

# Tool spans are opened and closed from separate executor hooks that may run
# in different contexts, so they are never attached as the current span.
ALL_ATTACH_SCOPES: FrozenSet[str] = frozenset(
    {SCOPE_SESSION, SCOPE_NODE, SCOPE_ITERATION, SCOPE_LLM}
)
# When sharing the process with Langfuse, only the leaf model-call span is
# made current, so Langfuse's own nesting is left untouched.
SHARED_ATTACH_SCOPES: FrozenSet[str] = frozenset({SCOPE_LLM})

_SPAN_STACK: ContextVar[Tuple[Span, ...]] = ContextVar("mas_otel_span_stack", default=())

_SCALAR = (str, bool, int, float)


@dataclass
class _Observation:
    span: Span
    error_type: Optional[str] = None
    usage: Dict[str, int] = field(default_factory=dict)
    success: Optional[bool] = None


def _scalar_attributes(prefix: str, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        f"{prefix}{k}": v
        for k, v in (metadata or {}).items()
        if isinstance(v, _SCALAR)
    }


class OtelTracingService(TracingService):
    """Tracing service emitting OpenTelemetry spans and metrics."""

    def __init__(
        self,
        *,
        tracer_provider: Optional[trace.TracerProvider] = None,
        meter_provider: Optional[metrics.MeterProvider] = None,
        attach_scopes: FrozenSet[str] = ALL_ATTACH_SCOPES,
    ) -> None:
        # Without explicit providers the global proxies are used, so the
        # service can be built before init_telemetry() installs the SDK.
        self._tracer = trace.get_tracer(INSTRUMENTATION_NAME, tracer_provider=tracer_provider)
        meter = metrics.get_meter(INSTRUMENTATION_NAME, meter_provider=meter_provider)
        self._attach = attach_scopes

        self._llm_duration = meter.create_histogram(
            "gen_ai.client.operation.duration",
            unit="s",
            description="GenAI operation duration",
        )
        self._token_usage = meter.create_histogram(
            "gen_ai.client.token.usage",
            unit="{token}",
            description="Number of input and output tokens used",
        )
        self._node_duration = meter.create_histogram(
            "mas.node.duration", unit="s", description="Workflow node execution duration",
        )
        self._session_duration = meter.create_histogram(
            "mas.session.duration", unit="s", description="Workflow session (run) execution duration",
        )
        self._tool_calls = meter.create_counter(
            "mas.tool.calls", unit="{call}", description="Tool calls by outcome",
        )

    @property
    def enabled(self) -> bool:
        return True

    # ── core span helper ─────────────────────────────────────────

    @contextmanager
    def _observe(
        self,
        scope: str,
        name: str,
        attributes: Dict[str, Any],
    ) -> Iterator[_Observation]:
        stack = _SPAN_STACK.get()
        parent = trace.set_span_in_context(stack[-1]) if stack else None
        span = self._tracer.start_span(
            name,
            context=parent,
            kind=SpanKind.CLIENT if scope == SCOPE_LLM else SpanKind.INTERNAL,
            attributes={k: v for k, v in attributes.items() if v is not None and v != ""},
        )
        obs = _Observation(span=span)
        stack_token = _SPAN_STACK.set(stack + (span,))
        ctx_token = (
            otel_context.attach(trace.set_span_in_context(span))
            if scope in self._attach else None
        )
        try:
            yield obs
        except GeneratorExit:
            # A consumer stopped iterating a stream early: not an error.
            raise
        except BaseException as exc:
            obs.error_type = type(exc).__qualname__
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, f"{obs.error_type}: {exc}"))
            raise
        finally:
            if obs.error_type:
                span.set_attribute("error.type", obs.error_type)
            if ctx_token is not None:
                otel_context.detach(ctx_token)
            try:
                _SPAN_STACK.reset(stack_token)
            except ValueError:
                # Closed from a different context (streams, executor hooks).
                _SPAN_STACK.set(stack)
            span.end()

    @staticmethod
    def _make_handle(obs: _Observation) -> ObservationHandle:
        def _update(
            *,
            output: Any = None,
            usage_details: Optional[Dict[str, Any]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            level: Optional[str] = None,
            status_message: Optional[str] = None,
        ) -> None:
            # ``output`` is deliberately ignored: no content on spans.
            span = obs.span
            if usage_details:
                for key in ("input_tokens", "output_tokens"):
                    value = usage_details.get(key)
                    if isinstance(value, int):
                        obs.usage[key] = value
                        span.set_attribute(f"gen_ai.usage.{key}", value)
            if metadata:
                success = metadata.get("success")
                if isinstance(success, bool):
                    obs.success = success
                span.set_attributes(_scalar_attributes("mas.", metadata))
            if level and level.upper() == "ERROR":
                obs.error_type = obs.error_type or "error"
                obs.success = False
                span.set_status(Status(StatusCode.ERROR, status_message or None))

        return ObservationHandle(_update_fn=_update)

    @staticmethod
    def _outcome(obs: _Observation) -> str:
        return "error" if obs.error_type or obs.success is False else "ok"

    # ── session ──────────────────────────────────────────────────

    @contextmanager
    def trace_session(
        self,
        session_id: str,
        user_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]:
        attrs = {
            "session.id": session_id,
            "mas.run.id": session_id,
            "user.id": user_id,
            **_scalar_attributes("mas.", metadata),
        }
        start = time.perf_counter()
        obs: Optional[_Observation] = None
        try:
            with self._observe(SCOPE_SESSION, "mas.session", attrs) as obs:
                yield self._make_handle(obs)
        finally:
            if obs is not None:
                self._session_duration.record(
                    time.perf_counter() - start, {"mas.outcome": self._outcome(obs)},
                )

    # ── node ─────────────────────────────────────────────────────

    @contextmanager
    def trace_node(
        self,
        node_uid: str,
        node_type: str,
        display_name: str = "",
    ) -> Iterator[ObservationHandle]:
        attrs = {
            "mas.node.uid": node_uid,
            "mas.node.type": node_type,
            "mas.node.name": display_name,
        }
        start = time.perf_counter()
        obs: Optional[_Observation] = None
        try:
            with self._observe(SCOPE_NODE, f"mas.node {display_name or node_uid}", attrs) as obs:
                yield self._make_handle(obs)
        finally:
            if obs is not None:
                self._node_duration.record(
                    time.perf_counter() - start,
                    {"mas.node.type": node_type, "mas.outcome": self._outcome(obs)},
                )

    # ── LLM call ─────────────────────────────────────────────────

    @contextmanager
    def trace_llm(
        self,
        model: str,
        provider: str,
        input_messages: Optional[List[Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]:
        # input_messages is deliberately ignored: no prompt content on spans.
        base = {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": provider,
            "gen_ai.request.model": model,
        }
        start = time.perf_counter()
        obs: Optional[_Observation] = None
        try:
            with self._observe(
                SCOPE_LLM, f"chat {model}", {**base, **_scalar_attributes("mas.", metadata)},
            ) as obs:
                yield self._make_handle(obs)
        finally:
            if obs is not None:
                metric_attrs = dict(base)
                if obs.error_type:
                    metric_attrs["error.type"] = obs.error_type
                self._llm_duration.record(time.perf_counter() - start, metric_attrs)
                for key, token_type in (("input_tokens", "input"), ("output_tokens", "output")):
                    if key in obs.usage:
                        self._token_usage.record(
                            obs.usage[key], {**base, "gen_ai.token.type": token_type},
                        )

    # ── tool call ────────────────────────────────────────────────

    @contextmanager
    def trace_tool(
        self,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> Iterator[ObservationHandle]:
        # tool_input is deliberately ignored: no tool arguments on spans.
        attrs = {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": tool_name,
        }
        obs: Optional[_Observation] = None
        try:
            with self._observe(SCOPE_TOOL, f"execute_tool {tool_name}", attrs) as obs:
                yield self._make_handle(obs)
        finally:
            if obs is not None:
                self._tool_calls.add(
                    1, {"gen_ai.tool.name": tool_name, "mas.outcome": self._outcome(obs)},
                )

    # ── agent iteration ──────────────────────────────────────────

    @contextmanager
    def trace_agent_iteration(
        self,
        iteration: int,
        strategy: str = "",
    ) -> Iterator[ObservationHandle]:
        attrs = {"mas.agent.iteration": iteration, "mas.agent.strategy": strategy}
        with self._observe(SCOPE_ITERATION, "mas.agent.iteration", attrs) as obs:
            yield self._make_handle(obs)

    # ── thread hand-off ─────────────────────────────────────────

    def bind_to_current_context(self, fn):
        ctx = otel_context.get_current()
        stack = _SPAN_STACK.get()

        def _bound(*args: Any, **kwargs: Any) -> Any:
            ctx_token = otel_context.attach(ctx)
            stack_token = _SPAN_STACK.set(stack)
            try:
                return fn(*args, **kwargs)
            finally:
                _SPAN_STACK.reset(stack_token)
                otel_context.detach(ctx_token)

        return _bound

    # ── flush ────────────────────────────────────────────────────

    def flush(self) -> None:
        # Spans are exported by the SDK's batch processor in the background
        # and flushed at interpreter exit; forcing a flush after every node
        # (as the port's callers do) would block the worker on the exporter.
        pass
