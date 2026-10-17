"""OpenTelemetry instrumentation of retrieval and ingestion (opt-in)."""
import json
from unittest.mock import MagicMock, PropertyMock, create_autospec

import numpy as np
import pytest

pytest.importorskip("opentelemetry.sdk")

from core.data_sources.service import DataSourceService
from core.monitoring.service import MonitoringService
from core.pipeline.domain.port import SourcePipelinePort
from core.pipeline.executor import PipelineExecutor
from core.pipeline.service import PipelineService
from core.retrieval.service import RetrievalService
from core.vector.domain.embedder import EmbeddingGenerator
from core.vector.domain.model import SearchResult
from core.vector.domain.repository import VectorRepository
from infrastructure.retrieval.source_filter_resolver import SourceFilterResolver
from opentelemetry import propagate, trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from global_utils import telemetry

_OTEL_ENV = (
    "OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "UNIFAI_OTEL_ENABLED", "OTEL_SDK_DISABLED",
)


@pytest.fixture
def clean_env(monkeypatch):
    for var in _OTEL_ENV:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(scope="module")
def _provider():
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


@pytest.fixture
def spans(_provider):
    _provider.clear()
    return _provider


@pytest.mark.unit
class TestEnableRule:
    def test_off_without_env(self, clean_env):
        before = trace.get_tracer_provider()
        assert telemetry.is_enabled() is False
        assert telemetry.init_telemetry("rag-server") is False
        assert trace.get_tracer_provider() is before

    def test_on_with_standard_endpoint(self, clean_env, monkeypatch):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
        assert telemetry.is_enabled() is True

    def test_explicit_flag_and_kill_switches(self, clean_env, monkeypatch):
        monkeypatch.setenv("UNIFAI_OTEL_ENABLED", "true")
        assert telemetry.is_enabled() is True
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
        monkeypatch.setenv("UNIFAI_OTEL_ENABLED", "false")
        assert telemetry.is_enabled() is False
        monkeypatch.setenv("UNIFAI_OTEL_ENABLED", "true")
        monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
        assert telemetry.is_enabled() is False

    def test_flask_not_instrumented_when_off(self, clean_env):
        app = MagicMock()
        assert telemetry.instrument_flask_app(app) is False


def _retrieval(results):
    embedder = create_autospec(EmbeddingGenerator, instance=True)
    embedder.generate_query_embedding.return_value = np.array([0.1, 0.2])
    repo = create_autospec(VectorRepository, instance=True)
    repo.search.return_value = results
    resolver = create_autospec(SourceFilterResolver, instance=True)
    resolver.resolve.return_value = None
    return RetrievalService(embedder, repo, resolver, source_type="DOCUMENT"), repo


@pytest.mark.unit
class TestRetrievalSpans:
    def test_search_span_tree_and_attributes(self, spans):
        service, repo = _retrieval([
            SearchResult(id="1", score=0.9, content="SECRET CHUNK", metadata={}),
            SearchResult(id="2", score=0.8, content="SECRET CHUNK", metadata={}),
        ])
        seen = {}

        def _search(**kwargs):
            carrier = {}
            propagate.inject(carrier)
            seen["traceparent"] = carrier.get("traceparent")
            return repo.search.return_value

        repo.search.side_effect = _search

        out = service.search("SECRET QUERY", owner_id="alice", limit=3, tags=["t"])

        assert len(out) == 2
        by_name = {s.name: s for s in spans.get_finished_spans()}
        root = by_name["rag.search"]
        assert by_name["rag.embed_query"].parent.span_id == root.context.span_id
        vector = by_name["rag.vector_search"]
        assert vector.parent.span_id == root.context.span_id
        assert root.attributes["rag.source_type"] == "DOCUMENT"
        assert root.attributes["rag.top_k"] == 3
        assert root.attributes["rag.filter.tags.count"] == 1
        assert root.attributes["rag.results.count"] == 2
        # The vector store call runs inside the span: its context propagates.
        assert seen["traceparent"].split("-")[2] == format(vector.context.span_id, "016x")
        dumped = json.dumps([dict(s.attributes) for s in by_name.values()])
        assert "SECRET" not in dumped and "alice" not in dumped

    def test_search_failure_marks_span(self, spans):
        service, repo = _retrieval([])
        repo.search.side_effect = RuntimeError("qdrant down")
        with pytest.raises(RuntimeError):
            service.search("q", owner_id="o")
        root = {s.name: s for s in spans.get_finished_spans()}["rag.search"]
        assert root.status.status_code == StatusCode.ERROR


@pytest.mark.unit
class TestPipelineSpans:
    def test_pipeline_step_spans(self, spans, build_context):
        handler = create_autospec(SourcePipelinePort, instance=True)
        type(handler).source_type = PropertyMock(return_value="DOCUMENT")
        handler.collect.return_value = {}
        handler.process.return_value = {}
        handler.chunk_and_embed.return_value = [MagicMock()]
        handler.get_summary.return_value = {}
        repo = create_autospec(VectorRepository, instance=True)
        repo.store.return_value = 4
        executor = PipelineExecutor(
            pipeline_service=create_autospec(PipelineService, instance=True),
            monitoring_service=create_autospec(MonitoringService, instance=True),
            data_source_service=create_autospec(DataSourceService, instance=True),
            vector_repository=MagicMock(return_value=repo),
        )

        assert executor.execute(handler, build_context()) == 4

        by_name = {s.name: s for s in spans.get_finished_spans()}
        root = by_name["rag.pipeline"]
        for step in ("collect", "process", "chunk_and_embed", "store"):
            assert by_name[f"rag.pipeline.{step}"].parent.span_id == root.context.span_id
        assert root.attributes["rag.source_type"] == "DOCUMENT"
        assert root.attributes["rag.pipeline.id"] == "pipe_1"
        assert root.attributes["rag.pipeline.embeddings.stored"] == 4
        assert "report.pdf" not in json.dumps(dict(root.attributes))


@pytest.mark.unit
class TestBootstrap:
    def test_helpers_degrade_without_the_otel_package(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "opentelemetry", None)
        with telemetry.start_span("x", {"a": 1}) as span:
            span.set_attribute("b", 2)
        telemetry.histogram("h").record(1.0)
        telemetry.counter("c").add(1)

    def test_init_installs_sdk_and_instruments_clients(self, tmp_path):
        """Run in a subprocess: the global provider can be set once per process."""
        import os
        import subprocess
        import sys

        script = (
            "from global_utils.telemetry import init_telemetry\n"
            "from opentelemetry import trace\n"
            "from opentelemetry.sdk.trace import TracerProvider\n"
            "assert init_telemetry('rag-server', celery=True) is True\n"
            "assert init_telemetry('rag-server') is True\n"
            "p = trace.get_tracer_provider()\n"
            "assert isinstance(p, TracerProvider), p\n"
            "assert p.resource.attributes['service.name'] == 'custom-name'\n"
            "import requests\n"
            "assert hasattr(requests.Session.send, '__wrapped__') or "
            "'opentelemetry' in repr(requests.Session.send)\n"
            "print('ok')\n"
        )
        env = {
            **os.environ,
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:9",
            "OTEL_SERVICE_NAME": "custom-name",
            "OTEL_METRICS_EXPORTER": "none",
            "OTEL_TRACES_EXPORTER": "none",
            "PYTHONPATH": os.pathsep.join(sys.path),
        }
        out = subprocess.run(
            [sys.executable, "-c", script], check=False, env=env, capture_output=True, text=True, timeout=60,
        )
        assert out.returncode == 0, out.stderr
        assert out.stdout.strip() == "ok"
