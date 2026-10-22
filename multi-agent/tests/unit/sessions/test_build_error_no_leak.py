"""The user-visible build error never carries config values, hosts, URLs, ids or credentials."""
from unittest.mock import MagicMock

import pytest
from temporalio.exceptions import ApplicationError

from mas.elements.common.exceptions import PluginConfigurationError
from mas.engine.distributed.node_executor import NodeExecutor
from mas.session.domain.exceptions import (
    SessionBuildError, scrub_error_message, session_build_error_message,
)
from mas.session.domain.models import SessionMeta
from mas.session.domain.status import SessionStatus
from mas.session.execution.lifecycle import SessionLifecycle
from mas.session.service import SessionService
from mas.elements.llms.common.chat.message import ERROR_METADATA_KEY, Role

SENSITIVE = [
    "scope-7f3a91c2-aaaa-bbbb-cccc-0123456789ab",
    "qdrant.internal.example",
    "mongo-prod.cluster.local",
    "hunter2",
    "tenant_db_name",
    "/srv/secret/path",
    "sk-live-abcdef123456",
]
CONFIG = {
    "scope_id": SENSITIVE[0],
    "qdrant_url": f"https://admin:{SENSITIVE[3]}@{SENSITIVE[1]}:6333",
    "mongo_db": SENSITIVE[4],
    "mongo_collection": "col",
    "api_key": SENSITIVE[6],
}


def _memory_error() -> PluginConfigurationError:
    """Mimic the real chain: connection error -> memory factory -> category builder."""
    root = ConnectionRefusedError(111, f"[Errno 111] Connection refused to {SENSITIVE[2]}:27017 {SENSITIVE[5]}")
    inner = PluginConfigurationError(f"MemoryToolFactory.create() failed: {root}", CONFIG)
    inner.__cause__ = root
    outer = PluginConfigurationError(
        f"MemoryToolFactory.create() failed: {inner}", CONFIG, category="tool", element_type="memory",
    )
    outer.__cause__ = inner
    return outer


def _assert_clean(text: str) -> None:
    for item in SENSITIVE + ["config=", "://"]:
        assert item not in text, (item, text)
    assert len(text) <= 200


def test_message_uses_structured_fields_only():
    msg = session_build_error_message(_memory_error())
    _assert_clean(msg)
    assert "Errno" not in msg and "{" not in msg
    assert "tool 'memory'" in msg
    assert "dependency unreachable" in msg
    assert "ConnectionRefusedError" in msg


def test_validation_error_is_reported_as_invalid_configuration():
    err = PluginConfigurationError("rejects", CONFIG, category="llm", element_type="openai")
    assert "invalid configuration" in session_build_error_message(err)


def test_without_element_type_only_the_node_uid_is_used():
    msg = session_build_error_message(RuntimeError(f"password={SENSITIVE[3]}"), uid="n1")
    assert msg.startswith("Session build failed for node 'n1'")
    _assert_clean(msg)
    assert "node 'bad uid/with://url'" not in session_build_error_message(RuntimeError(), uid="bad uid/with://url")


@pytest.mark.parametrize("raw", [
    f"boom | config={CONFIG!r}",
    f"cannot reach https://u:{SENSITIVE[3]}@{SENSITIVE[1]}:6333/x",
    f"dial {SENSITIVE[2]}:27017 failed",
    f"token={SENSITIVE[6]} used in {SENSITIVE[5]}",
    f"scope {SENSITIVE[0]}",
])
def test_scrubber_strips_urls_hosts_tokens_paths_and_ids(raw):
    _assert_clean(scrub_error_message(raw))


def test_scrubber_keeps_a_plain_safe_message_and_caps_length():
    safe = "Session build failed for tool 'memory': invalid configuration (PluginConfigurationError)"
    assert scrub_error_message(safe) == safe
    assert len(scrub_error_message("x " * 500)) == 200


def test_session_build_error_scrubs_a_leaky_message():
    _assert_clean(SessionBuildError("s-1", str(_memory_error())).message)


def _service(error):
    record = MagicMock()
    record.metadata = SessionMeta()
    record.status = SessionStatus.PENDING
    record.graph_state.messages = []
    manager = MagicMock()
    manager.get_session.side_effect = error
    manager.get_record.return_value = record
    engine = MagicMock()
    return SessionService(manager, MagicMock(), MagicMock(), background_engine=engine), record


@pytest.mark.parametrize("call", ["run", "submit"])
def test_stored_and_returned_messages_are_clean_and_chat_message_added(call):
    svc, record = _service(_memory_error())

    with pytest.raises(SessionBuildError) as exc:
        getattr(svc, call)("s-1", {})

    for text in (exc.value.message, str(exc.value), record.metadata.status_message,
                 record.metadata.error["message"]):
        _assert_clean(text)
    (msg,) = record.graph_state.messages
    assert msg.role == Role.ASSISTANT
    assert msg.metadata[ERROR_METADATA_KEY] == {"type": "session_build_failed", "message": exc.value.message}
    _assert_clean(msg.content)
    _assert_clean(msg.metadata[ERROR_METADATA_KEY]["message"])


def test_full_detail_stays_in_the_server_log(caplog):
    svc, _ = _service(_memory_error())
    with caplog.at_level("ERROR"), pytest.raises(SessionBuildError):
        svc.run("s-1", {})
    assert any(r.exc_info and SENSITIVE[3] in str(r.exc_info[1]) for r in caplog.records)


def test_worker_path_and_temporal_conversion_are_clean():
    from inbound.temporal.activities.graph_node_activities import _as_non_retryable
    factory = MagicMock()
    factory.build_runtime_plan.side_effect = _memory_error()
    executor = NodeExecutor(session_factory=factory, tracing_service=MagicMock())
    bp = {"name": "mini", "description": "", "plan": [], "providers": [], "llms": [],
          "retrievers": [], "tools": [], "nodes": []}
    ctx = MagicMock(session_id="s-1")

    with pytest.raises(SessionBuildError) as exc:
        executor._execute_node_inner("n1", bp, None, MagicMock(), None, ctx)

    _assert_clean(exc.value.message)
    out = _as_non_retryable(exc.value)
    assert isinstance(out, ApplicationError) and out.non_retryable
    _assert_clean(out.message)


def test_lifecycle_fail_scrubs_and_appends_chat_message():
    record = MagicMock()
    record.metadata = SessionMeta()
    record.status = SessionStatus.RUNNING
    record.graph_state.messages = []
    leaky = SessionBuildError("s-1", "ok")
    leaky.message = str(_memory_error())  # simulate a message that bypassed construction

    SessionLifecycle(MagicMock()).fail(record, leaky)

    _assert_clean(record.metadata.error["message"])
    _assert_clean(record.metadata.status_message)
    assert record.graph_state.messages[0].metadata[ERROR_METADATA_KEY]["type"] == "session_build_failed"
