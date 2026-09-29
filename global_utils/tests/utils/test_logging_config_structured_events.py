"""Tests for structured-event logging and message->event auto-fill in logging_config."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

import pytest

import global_utils.utils.logging_config as lc


@pytest.fixture(autouse=True)
def _reset_logging():
    lc._CONFIGURED = False
    lc.set_request_id(None)
    lc.set_session_id(None)
    os.environ.pop("OTEL_LOGS_ENABLED", None)
    yield
    lc._CONFIGURED = False
    lc.set_request_id(None)
    lc.set_session_id(None)
    logging.getLogger().handlers.clear()


def test_structured_event_call_sets_event_and_context_fields():
    """Standard logger call with a dotted event-name message: event/context
    are derived by JSONFormatter (see test_event_autofill_from_message)."""
    with tempfile.TemporaryDirectory() as d:
        os.environ["BACKEND_ENV"] = "production"
        lc.configure_logging("test-svc", log_dir=d, enable_file=True)
        lc.set_request_id("req-abc")
        lc.set_session_id("sess-1")
        log = logging.getLogger("test.structured_event")
        log.info("session.created", extra={"blueprint_id": "bp-1"})
        lines = Path(d, "app.log").read_text().strip().splitlines()
        payload = json.loads(lines[-1])
        assert payload["event"] == "session.created"
        assert payload["message"] == "session.created"
        assert payload["request_id"] == "req-abc"
        assert payload["session_id"] == "sess-1"
        assert payload["context"]["blueprint_id"] == "bp-1"


def test_event_autofill_from_message():
    formatter = lc.JSONFormatter("svc", "production", None, None)
    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname="", lineno=0,
        msg="phase.transition", args=(), exc_info=None,
    )
    payload = json.loads(formatter.format(record))
    assert payload["event"] == "phase.transition"


def test_blank_correlation_fields_are_omitted():
    formatter = lc.JSONFormatter("svc", "production", None, None)
    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname="", lineno=0,
        msg="plain message", args=(), exc_info=None,
    )
    record.event = " "
    record.request_id = ""
    record.session_id = "\t"

    payload = json.loads(formatter.format(record))

    assert "event" not in payload
    assert "request_id" not in payload
    assert "session_id" not in payload


def test_serialized_context_is_parsed_as_an_object():
    formatter = lc.JSONFormatter("svc", "production", None, None)
    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname="", lineno=0,
        msg="plain message", args=(), exc_info=None,
    )
    record.context = '{"duration_ms": 142, "step_type": "error"}'

    payload = json.loads(formatter.format(record))

    assert payload["context"] == {"duration_ms": 142, "step_type": "error"}


def test_successful_werkzeug_health_check_is_filtered_from_all_handlers():
    with tempfile.TemporaryDirectory() as d:
        os.environ["BACKEND_ENV"] = "production"
        lc.configure_logging("test-svc", log_dir=d, enable_file=True)
        access_log = logging.getLogger("werkzeug")

        access_log.info('127.0.0.1 - - [01/Jan/2026] "GET /api/health/ HTTP/1.1" 200 -')
        access_log.info('127.0.0.1 - - [01/Jan/2026] "GET /api/health/ HTTP/1.1" 500 -')

        payloads = [
            json.loads(line) for line in Path(d, "app.log").read_text().splitlines()
        ]
        messages = [payload["message"] for payload in payloads]
        assert not any('"GET /api/health/ HTTP/1.1" 200 -' in message for message in messages)
        assert any('"GET /api/health/ HTTP/1.1" 500 -' in message for message in messages)


def test_otel_resource_attributes_include_service_version_and_environment():
    attributes = lc._otel_resource_attributes("multi-agent", "production", "2026.09.14")

    assert attributes == {
        "service.name": "multi-agent",
        "deployment.environment.name": "production",
        "service.version": "2026.09.14",
    }


def test_otel_resource_attributes_omit_unset_optional_values():
    assert lc._otel_resource_attributes("multi-agent", None, None) == {
        "service.name": "multi-agent"
    }


def test_bind_correlation_ids_overwrites_missing_ids():
    lc.set_request_id("req-old")
    lc.set_session_id("sess-old")

    lc.bind_correlation_ids(None, "sess-2")
    assert lc.get_request_id() is None
    assert lc.get_session_id() == "sess-2"

    lc.bind_correlation_ids("req-new")
    assert lc.get_request_id() == "req-new"
    assert lc.get_session_id() is None

    lc.bind_correlation_ids("", "")
    assert lc.get_request_id() is None
    assert lc.get_session_id() is None
