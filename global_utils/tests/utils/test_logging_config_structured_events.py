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
