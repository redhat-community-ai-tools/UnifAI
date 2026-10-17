"""OpenTelemetry tracing adapter: span tree, GenAI attributes, propagation."""
from __future__ import annotations

import json
import threading

import pytest

pytest.importorskip("opentelemetry.sdk")

import httpx2
from mas.core.tracing import NoOpTracingService
from mas.core.tracing.composite import CompositeTracingService
from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.llms.openai_compatible.openai_compatible import OpenAICompatibleLLM
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPX2ClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from outbound.otel import SHARED_ATTACH_SCOPES, OtelTracingService


@pytest.fixture
def otel():
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[reader])
    service = OtelTracingService(tracer_provider=tracer_provider, meter_provider=meter_provider)
    return service, exporter, reader, tracer_provider


def _by_name(exporter):
    return {s.name: s for s in exporter.get_finished_spans()}


def _metrics(reader):
    data = reader.get_metrics_data()
    out = {}
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                out[m.name] = list(m.data.data_points)
    return out


def _completion_transport(captured: list):
    body = {
        "id": "cmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-test",
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "hello"},
        }],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }

    def handler(request):
        captured.append(request)
        return httpx2.Response(200, json=body)

    return httpx2.MockTransport(handler)


@pytest.mark.unit
class TestOtelSpanTree:
    def test_session_node_llm_tree_and_genai_attributes(self, otel):
        service, exporter, reader, _ = otel

        with service.trace_session("run-1", user_id="alice", metadata={"scope": "public"}):
            with service.trace_node("n1", "CustomAgentNode", display_name="Planner"):
                with service.trace_llm(
                    "gpt-test", "openai_compatible",
                    input_messages=[{"role": "user", "content": "SECRET PROMPT"}],
                ) as gen:
                    gen.update(
                        output="SECRET ANSWER",
                        usage_details={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
                    )
                with service.trace_tool("search", tool_input={"q": "SECRET ARG"}) as tool:
                    tool.update(output="SECRET RESULT", metadata={"success": True})

        spans = _by_name(exporter)
        session = spans["mas.session"]
        node = spans["mas.node Planner"]
        llm = spans["chat gpt-test"]
        tool = spans["execute_tool search"]

        assert session.parent is None
        assert node.parent.span_id == session.context.span_id
        assert llm.parent.span_id == node.context.span_id
        assert tool.parent.span_id == node.context.span_id
        assert {s.context.trace_id for s in spans.values()} == {session.context.trace_id}

        assert session.attributes["session.id"] == "run-1"
        assert session.attributes["mas.run.id"] == "run-1"
        assert session.attributes["user.id"] == "alice"
        assert session.attributes["mas.scope"] == "public"
        assert node.attributes["mas.node.type"] == "CustomAgentNode"
        assert node.attributes["mas.node.uid"] == "n1"
        assert llm.kind == trace.SpanKind.CLIENT
        assert llm.attributes["gen_ai.operation.name"] == "chat"
        assert llm.attributes["gen_ai.request.model"] == "gpt-test"
        assert llm.attributes["gen_ai.provider.name"] == "openai_compatible"
        assert llm.attributes["gen_ai.usage.input_tokens"] == 11
        assert llm.attributes["gen_ai.usage.output_tokens"] == 7
        assert tool.attributes["gen_ai.tool.name"] == "search"

        # No content (prompts, completions, tool args/results) on any span.
        dumped = json.dumps([dict(s.attributes) for s in spans.values()])
        assert "SECRET" not in dumped

        metrics = _metrics(reader)
        assert metrics["gen_ai.client.operation.duration"][0].count == 1
        tokens = {
            p.attributes["gen_ai.token.type"]: p.sum
            for p in metrics["gen_ai.client.token.usage"]
        }
        assert tokens == {"input": 11, "output": 7}
        assert metrics["mas.node.duration"][0].attributes == {
            "mas.node.type": "CustomAgentNode", "mas.outcome": "ok",
        }
        assert metrics["mas.tool.calls"][0].attributes["mas.outcome"] == "ok"
        # No run, session or user identifier on any metric.
        for points in metrics.values():
            for p in points:
                assert not {"session.id", "mas.run.id", "user.id"} & set(p.attributes)

    def test_session_continues_the_ambient_trace(self, otel):
        service, exporter, _, provider = otel
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("inbound-request") as req:
            with service.trace_session("run-2"):
                pass
        session = _by_name(exporter)["mas.session"]
        assert session.parent.span_id == req.get_span_context().span_id

    def test_errors_mark_span_and_metrics(self, otel):
        service, exporter, reader, _ = otel
        with pytest.raises(RuntimeError):
            with service.trace_session("run-3"):
                with service.trace_node("n1", "X"):
                    raise RuntimeError("boom")
        spans = _by_name(exporter)
        assert spans["mas.node n1"].status.status_code == StatusCode.ERROR
        assert spans["mas.node n1"].attributes["error.type"] == "RuntimeError"
        assert spans["mas.session"].status.status_code == StatusCode.ERROR
        points = _metrics(reader)["mas.session.duration"]
        assert points[0].attributes == {"mas.outcome": "error"}

    def test_handle_error_level_sets_status(self, otel):
        service, exporter, _, _ = otel
        with service.trace_tool("t") as h:
            h.update(level="ERROR", status_message="tool failed", metadata={"success": False})
        span = _by_name(exporter)["execute_tool t"]
        assert span.status.status_code == StatusCode.ERROR
        assert span.status.description == "tool failed"

    def test_bind_to_current_context_crosses_threads(self, otel):
        service, exporter, _, provider = otel
        tracer = provider.get_tracer("test")

        def work():
            with service.trace_session("run-4"):
                pass

        with tracer.start_as_current_span("inbound-request") as req:
            t = threading.Thread(target=service.bind_to_current_context(work))
            t.start()
            t.join()
        session = _by_name(exporter)["mas.session"]
        assert session.parent.span_id == req.get_span_context().span_id


@pytest.mark.unit
class TestOtelPropagation:
    def test_openai_compatible_llm_sends_traceparent_of_llm_span(self, otel):
        service, exporter, _, provider = otel
        captured: list = []
        http_client = httpx2.Client(transport=_completion_transport(captured))
        HTTPX2ClientInstrumentor.instrument_client(http_client, tracer_provider=provider)

        llm = OpenAICompatibleLLM(
            base_url="http://model-router.invalid/v1",
            model_name="gpt-test",
            tracing=service,
            http_client=http_client,
        )
        with service.trace_session("run-5"):
            with service.trace_node("n1", "CustomAgentNode"):
                reply = llm.chat([ChatMessage(role=Role.USER, content="hi")])

        assert reply.content == "hello"
        spans = exporter.get_finished_spans()
        llm_span = next(s for s in spans if s.name == "chat gpt-test")
        http_span = next(s for s in spans if s.kind == trace.SpanKind.CLIENT and s is not llm_span)
        assert http_span.parent.span_id == llm_span.context.span_id
        assert llm_span.attributes["gen_ai.usage.input_tokens"] == 11
        assert llm_span.attributes["gen_ai.usage.output_tokens"] == 7

        traceparent = captured[0].headers["traceparent"]
        _, trace_id, parent_id, _ = traceparent.split("-")
        assert int(trace_id, 16) == llm_span.context.trace_id
        assert int(parent_id, 16) == http_span.context.span_id

    def test_shared_mode_only_llm_span_is_current(self, otel):
        _, exporter, _, provider = otel
        service = OtelTracingService(
            tracer_provider=provider,
            meter_provider=MeterProvider(metric_readers=[InMemoryMetricReader()]),
            attach_scopes=SHARED_ATTACH_SCOPES,
        )
        with service.trace_session("run-6"):
            assert not trace.get_current_span().get_span_context().is_valid
            with service.trace_node("n1", "X"):
                with service.trace_llm("m", "p"):
                    current = trace.get_current_span()
        spans = _by_name(exporter)
        assert current.get_span_context().span_id == spans["chat m"].context.span_id
        assert spans["chat m"].parent.span_id == spans["mas.node n1"].context.span_id


class _RecordingTracing(NoOpTracingService):
    """A non-OTel backend that records the order of its enter/exit calls."""

    def __init__(self, log):
        self._log = log

    @property
    def enabled(self):
        return True

    def trace_session(self, session_id, user_id="", metadata=None):
        return self._cm("session")

    def trace_llm(self, model, provider, input_messages=None, metadata=None):
        return self._cm("llm")

    def _cm(self, scope):
        from contextlib import contextmanager

        @contextmanager
        def cm():
            self._log.append(f"other-enter-{scope}")
            from mas.core.tracing.noop import _NOOP_HANDLE
            yield _NOOP_HANDLE

        return cm()


@pytest.mark.unit
class TestComposite:
    def test_otel_tree_unaffected_by_other_backend_and_context_owner_order(self, otel):
        service, exporter, _, _ = otel
        log: list = []
        other = _RecordingTracing(log)
        composite = CompositeTracingService(context_owner=service, others=[other])

        with composite.trace_session("run-7") as h:
            # Owner entered first for the session: its span already exists.
            assert log == ["other-enter-session"]
            with composite.trace_node("n1", "X"):
                with composite.trace_llm("m", "p") as gen:
                    gen.update(usage_details={"input_tokens": 3, "output_tokens": 2})
                    # Owner entered last: the OTel LLM span is current.
                    assert trace.get_current_span().is_recording()
            h.update(metadata={"k": "v"})

        assert composite.enabled
        spans = _by_name(exporter)
        assert spans["mas.node n1"].parent.span_id == spans["mas.session"].context.span_id
        assert spans["chat m"].parent.span_id == spans["mas.node n1"].context.span_id
        assert spans["chat m"].attributes["gen_ai.usage.input_tokens"] == 3
        assert spans["mas.session"].attributes["mas.k"] == "v"


@pytest.mark.unit
class TestNoOpUnchanged:
    def test_noop_service_records_nothing_and_binds_identity(self):
        noop = NoOpTracingService()
        assert noop.enabled is False

        def fn():
            return 42

        assert noop.bind_to_current_context(fn) is fn
        with noop.trace_session("s") as h:
            with noop.trace_llm("m", "p") as g:
                g.update(usage_details={"input_tokens": 1})
            h.update(output="x")
        assert not trace.get_current_span().get_span_context().is_valid


@pytest.mark.unit
class TestContainerSelection:
    """_create_tracing_service picks backends from config + OTel env."""

    @staticmethod
    def _cfg(langfuse=False):
        from types import SimpleNamespace

        return SimpleNamespace(
            langfuse_enabled=langfuse,
            langfuse_secret_key="",
            langfuse_public_key="",
            langfuse_base_url="",
        )

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        for var in (
            "OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            "UNIFAI_OTEL_ENABLED", "OTEL_SDK_DISABLED",
        ):
            monkeypatch.delenv(var, raising=False)

    def test_noop_when_nothing_enabled(self):
        from bootstrap.container import AppContainer

        assert type(AppContainer._create_tracing_service(self._cfg())) is NoOpTracingService

    def test_otel_when_endpoint_set(self, monkeypatch):
        from bootstrap.container import AppContainer

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
        assert isinstance(AppContainer._create_tracing_service(self._cfg()), OtelTracingService)

    def test_sdk_disabled_wins(self, monkeypatch):
        from bootstrap.container import AppContainer

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
        monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
        assert type(AppContainer._create_tracing_service(self._cfg())) is NoOpTracingService


@pytest.mark.unit
class TestLangfuseCoexistence:
    """Langfuse (itself OTel-based) and OTel enabled at once."""

    def test_both_trees_stay_intact_and_providers_stay_separate(self, otel, monkeypatch):
        pytest.importorskip("langfuse")
        from outbound.langfuse.langfuse_tracing_service import LangfuseTracingService

        global_before = trace.get_tracer_provider()
        _, otel_exporter, _, provider = otel
        otel_shared = OtelTracingService(
            tracer_provider=provider,
            meter_provider=MeterProvider(metric_readers=[InMemoryMetricReader()]),
            attach_scopes=SHARED_ATTACH_SCOPES,
        )

        lf_exporter = InMemorySpanExporter()
        lf_provider = TracerProvider()
        lf_provider.add_span_processor(SimpleSpanProcessor(lf_exporter))
        langfuse = LangfuseTracingService(
            secret_key="sk-test",
            public_key="pk-test",
            base_url="http://127.0.0.1:9",  # unreachable: auth check just warns
            tracer_provider=lf_provider,
        )
        composite = CompositeTracingService(context_owner=otel_shared, others=[langfuse])

        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("inbound-request") as req:
            with composite.trace_session("run-8", user_id="bob"):
                with composite.trace_node("n1", "X", display_name="Planner"):
                    with composite.trace_llm("m", "openai_compatible") as gen:
                        gen.update(usage_details={"input_tokens": 5, "output_tokens": 4})

        # Langfuse did not take over the global provider.
        assert trace.get_tracer_provider() is global_before

        o = _by_name(otel_exporter)
        assert o["mas.session"].parent.span_id == req.get_span_context().span_id
        assert o["mas.node Planner"].parent.span_id == o["mas.session"].context.span_id
        assert o["chat m"].parent.span_id == o["mas.node Planner"].context.span_id
        assert {s.context.trace_id for s in o.values()} == {req.get_span_context().trace_id}

        lf = {s.name: s for s in lf_exporter.get_finished_spans()}
        lf_session = lf["session:run-8"]
        assert lf["Planner"].parent.span_id == lf_session.context.span_id
        assert lf["openai_compatible/m"].parent.span_id == lf["Planner"].context.span_id
        # Langfuse keeps its own (session-seeded) trace, separate from OTel's.
        assert lf_session.context.trace_id != req.get_span_context().trace_id
        lf_ids = {s.context.span_id for s in lf.values()}
        assert not lf_ids & {s.context.span_id for s in o.values()}
