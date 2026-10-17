"""Optional OpenTelemetry support (inert unless enabled by the environment)."""
from global_utils.telemetry.otel import (
    counter,
    histogram,
    init_telemetry,
    instrument_celery,
    instrument_flask_app,
    instrument_http_clients,
    is_enabled,
    otel_available,
    start_span,
)

__all__ = [
    "counter",
    "histogram",
    "init_telemetry",
    "instrument_celery",
    "instrument_flask_app",
    "instrument_http_clients",
    "is_enabled",
    "otel_available",
    "start_span",
]
