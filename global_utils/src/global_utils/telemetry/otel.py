"""Optional OpenTelemetry bootstrap shared by the UnifAI Python services.

Telemetry is **off by default**.  It turns on when the standard OTLP
endpoint variable is set (``OTEL_EXPORTER_OTLP_ENDPOINT`` or
``OTEL_EXPORTER_OTLP_TRACES_ENDPOINT``) or when ``UNIFAI_OTEL_ENABLED`` is
truthy.  ``UNIFAI_OTEL_ENABLED=false`` or the standard
``OTEL_SDK_DISABLED=true`` force it off.

Everything else follows the standard OpenTelemetry environment variables,
read by the SDK and the OTLP exporters themselves:

* ``OTEL_SERVICE_NAME`` / ``OTEL_RESOURCE_ATTRIBUTES``
* ``OTEL_EXPORTER_OTLP_PROTOCOL`` (``grpc`` default, or ``http/protobuf``)
* ``OTEL_EXPORTER_OTLP_HEADERS``, ``OTEL_EXPORTER_OTLP_CERTIFICATE`` ...
* ``OTEL_TRACES_SAMPLER`` / ``OTEL_TRACES_SAMPLER_ARG``
* ``OTEL_TRACES_EXPORTER=none`` / ``OTEL_METRICS_EXPORTER=none``

The OpenTelemetry packages are optional at import time: when they are not
installed every helper in this module degrades to a no-op, so a service
never fails to start because of telemetry.

Prompts, completions, request bodies and headers are never recorded by the
helpers here; the HTTP instrumentations record method, URL and status only.
"""
from __future__ import annotations

import importlib.util
import logging
import os
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Mapping, Optional

logger = logging.getLogger(__name__)

ENABLE_FLAG = "UNIFAI_OTEL_ENABLED"
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}

_lock = threading.Lock()
_initialized_pid: Optional[int] = None
_instrumented: set[str] = set()


def _env_flag(name: str) -> Optional[bool]:
    value = os.getenv(name, "").strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    return None


def otel_available() -> bool:
    """True when the OpenTelemetry SDK is importable."""
    try:
        return importlib.util.find_spec("opentelemetry.sdk.trace") is not None
    except (ImportError, ValueError):  # parent package missing or stubbed out
        return False


def is_enabled() -> bool:
    """Decide from the environment whether telemetry should be exported."""
    if _env_flag("OTEL_SDK_DISABLED") is True:
        return False
    flag = _env_flag(ENABLE_FLAG)
    if flag is not None:
        return flag
    return bool(
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    )


def _protocol(signal: str) -> str:
    return (
        os.getenv(f"OTEL_EXPORTER_OTLP_{signal}_PROTOCOL")
        or os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL")
        or "grpc"
    ).strip().lower()


def _span_exporter():
    if _protocol("TRACES") == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
    else:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
    return OTLPSpanExporter()


def _metric_exporter():
    if _protocol("METRICS") == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
    else:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )
    return OTLPMetricExporter()


def _resource(default_service_name: str):
    from opentelemetry.sdk.resources import Resource

    attributes: Dict[str, Any] = {}
    # Resource.create() lets explicit attributes win over the environment,
    # so only supply a default when the operator did not name the service.
    env_attrs = os.getenv("OTEL_RESOURCE_ATTRIBUTES", "")
    if not os.getenv("OTEL_SERVICE_NAME") and "service.name=" not in env_attrs:
        attributes["service.name"] = default_service_name
    return Resource.create(attributes)


def init_telemetry(default_service_name: str, *, celery: bool = False) -> bool:
    """Install the global tracer/meter providers and client instrumentations.

    Idempotent per process.  Call it from the process entry point (the
    Flask app factory, the Temporal worker, the Celery app) rather than at
    import time, so that pre-forking servers initialise each worker.

    Returns True when telemetry is active after the call.
    """
    global _initialized_pid
    if not is_enabled():
        return False
    if not otel_available():
        logger.warning(
            "OpenTelemetry is enabled by the environment but the SDK is not installed; "
            "telemetry stays off"
        )
        return False

    with _lock:
        if _initialized_pid == os.getpid():
            return True
        try:
            _install_providers(default_service_name)
        except Exception:  # never let telemetry break service start-up
            logger.exception("OpenTelemetry initialisation failed; telemetry stays off")
            return False
        _initialized_pid = os.getpid()

    instrument_http_clients()
    if celery:
        instrument_celery()
    return True


def _install_providers(default_service_name: str) -> None:
    from opentelemetry import metrics, trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = _resource(default_service_name)

    current = trace.get_tracer_provider()
    if isinstance(current, trace.ProxyTracerProvider):
        # The sampler comes from OTEL_TRACES_SAMPLER{,_ARG} (SDK default).
        provider = TracerProvider(resource=resource)
        if os.getenv("OTEL_TRACES_EXPORTER", "otlp").strip().lower() != "none":
            provider.add_span_processor(BatchSpanProcessor(_span_exporter()))
        trace.set_tracer_provider(provider)
    else:
        logger.info("A global TracerProvider is already installed; reusing it")

    metrics_on = os.getenv("OTEL_METRICS_EXPORTER", "otlp").strip().lower() != "none"
    if metrics_on and not isinstance(metrics.get_meter_provider(), MeterProvider):
        reader = PeriodicExportingMetricReader(_metric_exporter())
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))

    logger.info(
        "OpenTelemetry enabled",
        extra={
            "otel_service_name": resource.attributes.get("service.name"),
            "otel_traces_protocol": _protocol("TRACES"),
        },
    )


def _instrument_once(key: str, fn) -> None:
    if key in _instrumented:
        return
    try:
        fn()
    except ImportError:
        logger.debug("OpenTelemetry instrumentation %s not installed; skipped", key)
        return
    except Exception:
        logger.warning("OpenTelemetry instrumentation %s failed", key, exc_info=True)
        return
    _instrumented.add(key)


def instrument_http_clients() -> None:
    """Propagate ``traceparent`` on outbound requests / httpx / httpx2 calls."""

    def _requests() -> None:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        RequestsInstrumentor().instrument()

    def _httpx() -> None:
        if importlib.util.find_spec("httpx") is None:
            raise ImportError("httpx")
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()

    def _httpx2() -> None:
        # Recent openai / anthropic SDKs are built on httpx2.
        if importlib.util.find_spec("httpx2") is None:
            raise ImportError("httpx2")
        from opentelemetry.instrumentation.httpx import HTTPX2ClientInstrumentor

        HTTPX2ClientInstrumentor().instrument()

    _instrument_once("requests", _requests)
    _instrument_once("httpx", _httpx)
    _instrument_once("httpx2", _httpx2)


def instrument_celery() -> None:
    """Propagate context producer -> worker and span every Celery task."""

    def _celery() -> None:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()

    _instrument_once("celery", _celery)


def instrument_flask_app(app: Any) -> bool:
    """Add server spans (and inbound ``traceparent`` extraction) to a Flask app.

    No-op unless :func:`init_telemetry` activated telemetry in this process.
    ``OTEL_PYTHON_FLASK_EXCLUDED_URLS`` defaults to the health endpoints.
    """
    if _initialized_pid != os.getpid():
        return False
    try:
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
    except ImportError:
        logger.warning("opentelemetry-instrumentation-flask not installed; Flask spans skipped")
        return False
    os.environ.setdefault("OTEL_PYTHON_FLASK_EXCLUDED_URLS", "health,healthz,readyz,livez")
    FlaskInstrumentor().instrument_app(app)
    return True


# ---------------------------------------------------------------------------
# Helpers for hand-written spans and metrics
# ---------------------------------------------------------------------------

class _NoOpSpan:
    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_attributes(self, attributes: Mapping[str, Any]) -> None:
        pass

    def record_exception(self, exc: BaseException) -> None:
        pass

    def is_recording(self) -> bool:
        return False


_NOOP_SPAN = _NoOpSpan()


def _clean(attributes: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    return {k: v for k, v in (attributes or {}).items() if v is not None}


@contextmanager
def start_span(
    name: str,
    attributes: Optional[Mapping[str, Any]] = None,
    *,
    tracer_name: str = "unifai",
) -> Iterator[Any]:
    """Open a span under the current context, or yield a no-op span.

    When the API is installed but no provider is configured the global
    no-op provider makes this effectively free.  Exceptions are recorded
    and the span status set to ERROR, then re-raised.
    """
    try:
        from opentelemetry import trace
    except ImportError:
        yield _NOOP_SPAN
        return

    tracer = trace.get_tracer(tracer_name)
    with tracer.start_as_current_span(name, attributes=_clean(attributes)) as span:
        yield span


class _NoOpInstrument:
    def add(self, amount: Any, attributes: Optional[Mapping[str, Any]] = None) -> None:
        pass

    def record(self, amount: Any, attributes: Optional[Mapping[str, Any]] = None) -> None:
        pass


_NOOP_INSTRUMENT = _NoOpInstrument()


def get_meter(name: str = "unifai") -> Any:
    """Return an OTel meter, or None when the API is missing."""
    try:
        from opentelemetry import metrics
    except ImportError:
        return None
    return metrics.get_meter(name)


def histogram(name: str, *, unit: str = "", description: str = "", meter_name: str = "unifai") -> Any:
    meter = get_meter(meter_name)
    if meter is None:
        return _NOOP_INSTRUMENT
    return meter.create_histogram(name, unit=unit, description=description)


def counter(name: str, *, unit: str = "", description: str = "", meter_name: str = "unifai") -> Any:
    meter = get_meter(meter_name)
    if meter is None:
        return _NOOP_INSTRUMENT
    return meter.create_counter(name, unit=unit, description=description)
