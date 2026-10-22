"""Server-side routing lookup: mocked gateway via httpx.MockTransport."""

from unittest.mock import MagicMock

import httpx
import pytest
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from mas.elements.llms.common.chat.message import RESPONSE_METADATA_KEY, ChatMessage, Role
from mas.elements.llms.openai_compatible.openai_compatible import OpenAICompatibleLLM

LOOKUP = "http://gw/v1/routing-decisions/{response_id}"
ROUTING = {"provider": "vllm-a", "model": "m1", "fallback_used": False}
USER = [ChatMessage(role=Role.USER, content="hi")]


class FakeForwarder:
    def __init__(self, headers=None, error=None):
        self._headers, self._error, self.calls = headers, error, []

    def headers(self, templates=None, forward_token=False):
        self.calls.append((templates, forward_token))
        if self._error:
            raise self._error
        return self._headers


def _llm(handler, forwarder="default", timeout=2.0, lookup=LOOKUP):
    if forwarder == "default":
        forwarder = FakeForwarder({"Authorization": "Bearer tok"})
    llm = OpenAICompatibleLLM(
        base_url="http://localhost:1/v1", model_name="m", tracing=MagicMock(),
        metadata_lookup_url=lookup, metadata_lookup_timeout=timeout,
        lookup_forwarder=forwarder,
    )
    llm._lookup_transport = httpx.MockTransport(handler)
    llm._client = MagicMock()
    return llm


def _completion(**extra):
    return ChatCompletion.model_validate({
        "id": "resp-1", "object": "chat.completion", "created": 1, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": "hello"}}],
        **extra,
    })


def _chunks(**extra):
    def c(content=None, finish=None, **kw):
        return ChatCompletionChunk.model_validate({
            "id": "resp-1", "object": "chat.completion.chunk", "created": 1, "model": "m",
            "choices": [{"index": 0, "finish_reason": finish,
                         "delta": {"content": content} if content else {}}], **kw})
    return iter([c("hel"), c("lo", **extra), c(finish="stop")])


def _ok(request):
    return httpx.Response(200, json=ROUTING)


def _chat(llm, **extra):
    llm._client.chat.completions.create.return_value = _completion(**extra)
    return llm.chat(USER)


def _stream_final(llm, **extra):
    llm._client.chat.completions.create.return_value = _chunks(**extra)
    return list(llm.stream(USER))[-1]


def test_success_attaches_routing_and_relays_identity_non_streaming():
    seen = {}

    def handler(request):
        seen["url"], seen["auth"] = str(request.url), request.headers.get("authorization")
        return httpx.Response(200, json=ROUTING)

    fwd = FakeForwarder({"Authorization": "Bearer tok"})
    msg = _chat(_llm(handler, fwd), x_provider="p")
    entry = msg.metadata[RESPONSE_METADATA_KEY]
    assert entry["routing"] == ROUTING
    assert entry["fields"] == {"x_provider": "p"}
    assert "lookup_url" not in entry
    assert seen == {"url": "http://gw/v1/routing-decisions/resp-1", "auth": "Bearer tok"}
    assert fwd.calls == [({}, True)]
    assert "tok" not in str(entry)


def test_success_streaming():
    final = _stream_final(_llm(_ok), x_provider="p")
    assert isinstance(final, ChatMessage)
    assert final.metadata[RESPONSE_METADATA_KEY]["routing"] == ROUTING


def test_routing_alone_is_enough_when_no_extra_fields():
    msg = _chat(_llm(_ok))
    assert msg.metadata[RESPONSE_METADATA_KEY]["routing"] == ROUTING


def test_timeout_is_swallowed():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    msg = _chat(_llm(handler), x_provider="p")
    entry = msg.metadata[RESPONSE_METADATA_KEY]
    assert "routing" not in entry and entry["fields"] == {"x_provider": "p"}
    assert msg.content == "hello"


def test_404_is_swallowed_and_adds_nothing_without_fields():
    msg = _chat(_llm(lambda r: httpx.Response(404)))
    assert msg.metadata == {}
    final = _stream_final(_llm(lambda r: httpx.Response(404)))
    assert final == "lo"  # plain text stream, no extra message


def test_non_json_body_is_swallowed():
    msg = _chat(_llm(lambda r: httpx.Response(200, text="not json")), x_provider="p")
    assert "routing" not in msg.metadata[RESPONSE_METADATA_KEY]


def test_no_url_means_no_request():
    calls = []
    llm = _llm(lambda r: calls.append(r) or httpx.Response(200, json=ROUTING), lookup=None)
    msg = _chat(llm, x_provider="p")
    assert calls == [] and "routing" not in msg.metadata[RESPONSE_METADATA_KEY]


@pytest.mark.parametrize("forwarder", [
    None,
    FakeForwarder(error=RuntimeError("no token")),
    FakeForwarder({}),
    FakeForwarder({"X-Only": "1"}),
])
def test_no_identity_means_no_request(forwarder):
    calls = []
    llm = _llm(lambda r: calls.append(r) or httpx.Response(200, json=ROUTING), forwarder)
    msg = _chat(llm, x_provider="p")
    assert calls == []
    assert "routing" not in msg.metadata[RESPONSE_METADATA_KEY]


# --- request id header -------------------------------------------------------

REQ_LOOKUP = "http://gw/v1/routing-decisions/{request_id}"
HEADER = "X-Request-Id"


def _llm_with_header(handler, header=HEADER, lookup=REQ_LOOKUP, forwarder="default"):
    llm = _llm(handler, forwarder=forwarder, lookup=lookup)
    llm._request_id_header = header
    return llm


def _sent_headers(llm):
    return llm._client.chat.completions.create.call_args.kwargs.get("extra_headers")


@pytest.mark.parametrize("mode", ["chat", "stream"])
def test_request_id_header_sent_and_used_for_lookup(mode):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json=ROUTING)

    llm = _llm_with_header(handler)
    msg = _chat(llm) if mode == "chat" else _stream_final(llm)
    rid = _sent_headers(llm)[HEADER]
    assert len(rid) == 32 and int(rid, 16) >= 0
    assert seen["url"] == f"http://gw/v1/routing-decisions/{rid}"
    entry = msg.metadata[RESPONSE_METADATA_KEY]
    assert entry["request_id"] == rid
    assert entry["response_id"] == "resp-1"
    assert entry["routing"] == ROUTING


@pytest.mark.parametrize("mode", ["chat", "stream"])
def test_request_id_header_merges_with_identity_headers(mode):
    fwd = FakeForwarder({"Authorization": "Bearer tok", "X-User": "u"})
    llm = _llm_with_header(_ok)
    llm._forwarder = fwd
    _chat(llm) if mode == "chat" else _stream_final(llm)
    headers = _sent_headers(llm)
    assert headers["Authorization"] == "Bearer tok"
    assert headers["X-User"] == "u"
    assert HEADER in headers


def test_request_id_is_fresh_per_call():
    llm = _llm_with_header(_ok)
    _chat(llm)
    first = _sent_headers(llm)[HEADER]
    _chat(llm)
    assert _sent_headers(llm)[HEADER] != first


@pytest.mark.parametrize("mode", ["chat", "stream"])
def test_response_id_template_unchanged_with_header_set(mode):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json=ROUTING)

    llm = _llm_with_header(handler, lookup=LOOKUP)
    _chat(llm) if mode == "chat" else _stream_final(llm)
    assert seen["url"] == "http://gw/v1/routing-decisions/resp-1"


@pytest.mark.parametrize("mode", ["chat", "stream"])
def test_no_header_when_unset(mode):
    llm = _llm_with_header(_ok, header="", lookup=LOOKUP)
    msg = _chat(llm) if mode == "chat" else _stream_final(llm)
    headers = _sent_headers(llm)
    assert not headers or HEADER not in headers
    assert "request_id" not in msg.metadata[RESPONSE_METADATA_KEY]


def test_request_id_template_without_header_fetches_nothing():
    called = []
    llm = _llm_with_header(lambda r: called.append(1) or httpx.Response(200, json=ROUTING),
                           header="")
    msg = _chat(llm)
    assert not called
    assert RESPONSE_METADATA_KEY not in msg.metadata
