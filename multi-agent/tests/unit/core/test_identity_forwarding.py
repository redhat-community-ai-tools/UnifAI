"""Identity forwarding: header templates, token resolution, element wiring."""
import asyncio
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from global_utils.redis.constants import identity_session_key
from mas.core.execution_context import (
    SESSION_TAGS_TAG,
    ExecutionContext,
    ExecutionContextHolder,
)
from mas.core.identity import resolve_identity
from mas.core.identity_forwarding import (
    ForwardedIdentityCredential,
    IdentityForwarder,
    IdentityTokenSource,
    IdentityTokenUnavailable,
    NullIdentityTokenSource,
    bind_current_node,
    current_node,
    render_header_templates,
)
from outbound.redis.identity_token_source import (
    RedisIdentityTokenSource,
    identity_binding_key,
)

# ── helpers ──────────────────────────────────────────────────────────────────

class FakeKV:
    def __init__(self):
        self.data = {}
        self.ttl = {}

    def hget(self, key):
        return dict(self.data.get(key, {}))

    def hset(self, key, value, ttl_seconds=None):
        self.data.setdefault(key, {}).update({k: str(v) for k, v in value.items()})
        self.ttl[key] = ttl_seconds


class StaticSource(IdentityTokenSource):
    def __init__(self, token="tok-123"):
        self.token = token
        self.calls = []

    def bind(self, session_id, identity_session_id, username):
        pass

    def get_access_token(self, session_id, username):
        self.calls.append((session_id, username))
        return self.token


def _holder(session_id="s-1", user="alice", tags=None):
    ctx = ExecutionContext(session_id=session_id, identity=resolve_identity(user, "user"))
    if tags is not None:
        ctx = ctx.with_session_tags(tags)
    holder = ExecutionContextHolder()
    holder.context = ctx
    return holder


# ── templates ────────────────────────────────────────────────────────────────

def test_render_resolves_static_and_templated_values():
    out = render_header_templates(
        {"X-Static": "v", "X-Session": "{session_id}", "X-Mix": "a-{user}-b"},
        {"session_id": "s-1", "user": "alice"},
    )
    assert out == {"X-Static": "v", "X-Session": "s-1", "X-Mix": "a-alice-b"}


def test_render_omits_header_with_unresolved_or_empty_variable():
    out = render_header_templates(
        {"X-Class": "{tag.classification}", "X-Empty": "{user}"},
        {"user": ""},
    )
    assert out == {}


# ── forwarder ────────────────────────────────────────────────────────────────

def test_forwarder_exposes_context_node_and_session_tags():
    fwd = IdentityForwarder(StaticSource(), _holder(tags={"classification": "C3"}))
    with bind_current_node("n1", "Researcher", "CustomAgentNode"):
        headers = fwd.headers(
            {"X-Agent": "{node_name}", "X-Class": "{tag.classification}", "X-Sess": "{session_id}"},
            forward_token=True,
        )
    assert headers == {
        "X-Agent": "Researcher",
        "X-Class": "C3",
        "X-Sess": "s-1",
        "Authorization": "Bearer tok-123",
    }
    assert current_node().uid == ""


def test_forwarder_fails_closed_without_token_source():
    fwd = IdentityForwarder(NullIdentityTokenSource(), _holder())
    with pytest.raises(IdentityTokenUnavailable):
        fwd.headers({}, forward_token=True)


def test_forwarder_fails_closed_without_execution_context():
    fwd = IdentityForwarder(StaticSource(), ExecutionContextHolder())
    with pytest.raises(IdentityTokenUnavailable):
        fwd.access_token()


def test_forwarder_headers_without_token_do_not_touch_source():
    src = StaticSource()
    fwd = IdentityForwarder(src, _holder())
    assert fwd.headers({"X-S": "{session_id}"}) == {"X-S": "s-1"}
    assert src.calls == []


def test_forwarded_credential_is_async_auth_credential():
    cred = ForwardedIdentityCredential(
        IdentityForwarder(StaticSource("t"), _holder()), {"X-U": "{user}"},
        target_url="http://mcp-gateway.zuno-ai-run.svc:8080/mcp",
    )
    assert asyncio.run(cred.get_headers()) == {"X-U": "alice", "Authorization": "Bearer t"}
    assert asyncio.run(cred.get_token()) == "t"
    assert asyncio.run(cred.attempt_recovery()).recovered is True


def test_with_session_tags_stringifies_and_nests():
    ctx = ExecutionContext(session_id="s", identity=resolve_identity("u", "user")).with_session_tags({"a": 1})
    assert ctx.tags[SESSION_TAGS_TAG] == {"a": "1"}


# ── redis token source ───────────────────────────────────────────────────────

def _seed_identity_session(kv, sid="idsid", expires_in=3600, session_in=7200, refresh="r-1"):
    now = time.time()
    kv.data[identity_session_key(sid)] = {
        "username": "alice",
        "access_token": "at-1",
        "refresh_token": refresh,
        "token_expires_at": str(now + expires_in),
        "session_expires_at": str(now + session_in),
    }


def test_bind_ttl_follows_identity_session_expiry():
    kv = FakeKV()
    _seed_identity_session(kv, session_in=100)
    RedisIdentityTokenSource(kv).bind("s-1", "idsid", "alice")
    assert kv.data[identity_binding_key("s-1")] == {"identity_session_id": "idsid", "username": "alice"}
    assert 0 < kv.ttl[identity_binding_key("s-1")] <= 100


def test_returns_valid_token_without_refresh():
    kv = FakeKV()
    _seed_identity_session(kv)
    src = RedisIdentityTokenSource(kv, http_post=MagicMock(side_effect=AssertionError("no refresh")))
    src.bind("s-1", "idsid", "alice")
    assert src.get_access_token("s-1", "alice") == "at-1"


def test_refuses_binding_of_another_user():
    kv = FakeKV()
    _seed_identity_session(kv)
    src = RedisIdentityTokenSource(kv)
    src.bind("s-1", "idsid", "alice")
    with pytest.raises(IdentityTokenUnavailable, match="another user"):
        src.get_access_token("s-1", "mallory")


def test_missing_binding_fails_closed():
    with pytest.raises(IdentityTokenUnavailable, match="no identity binding"):
        RedisIdentityTokenSource(FakeKV()).get_access_token("s-1", "alice")


def test_refreshes_expiring_token_and_writes_back():
    kv = FakeKV()
    _seed_identity_session(kv, expires_in=10)
    resp = MagicMock()
    resp.json.return_value = {"access_token": "at-2", "refresh_token": "r-2", "expires_in": 300}
    post = MagicMock(return_value=resp)
    src = RedisIdentityTokenSource(kv, token_url="https://kc/token", client_id="unifai", client_secret="s", http_post=post)
    src.bind("s-1", "idsid", "alice")

    assert src.get_access_token("s-1", "alice") == "at-2"
    sent = post.call_args.kwargs["data"]
    assert sent["grant_type"] == "refresh_token" and sent["refresh_token"] == "r-1"
    stored = kv.data[identity_session_key("idsid")]
    assert stored["access_token"] == "at-2" and stored["refresh_token"] == "r-2"
    assert float(stored["token_expires_at"]) > time.time() + 200


def test_expiring_token_without_refresh_config_fails_closed():
    kv = FakeKV()
    _seed_identity_session(kv, expires_in=10)
    src = RedisIdentityTokenSource(kv)
    src.bind("s-1", "idsid", "alice")
    with pytest.raises(IdentityTokenUnavailable, match="refresh is not configured"):
        src.get_access_token("s-1", "alice")


def test_ended_identity_session_fails_closed():
    kv = FakeKV()
    src = RedisIdentityTokenSource(kv)
    kv.data[identity_binding_key("s-1")] = {"identity_session_id": "gone", "username": "alice"}
    with pytest.raises(IdentityTokenUnavailable, match="ended"):
        src.get_access_token("s-1", "alice")


# ── element wiring ───────────────────────────────────────────────────────────

def test_openai_compatible_sends_forwarded_headers_per_call():
    from mas.core.element_deps import ElementBuildContext
    from mas.elements.llms.common.chat.message import ChatMessage, Role
    from mas.elements.llms.openai_compatible.config import OpenAICompatibleConfig
    from mas.elements.llms.openai_compatible.openai_compatible_factory import (
        OpenAICompatibleFactory,
    )

    cfg = OpenAICompatibleConfig(
        model_name="m", base_url="http://gw:8080/v1",
        forward_user_token=True, default_headers={"X-Zuno-Agent": "{node_name}"},
    )
    deps = ElementBuildContext(execution_ctx=_holder(), identity_token_source=StaticSource("user-tok"))
    tracing = MagicMock()
    tracing.trace_llm.return_value.__enter__ = MagicMock(return_value=MagicMock())
    tracing.trace_llm.return_value.__exit__ = MagicMock(return_value=False)
    deps.tracing_service = tracing
    llm = OpenAICompatibleFactory().create(cfg, deps=deps)

    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok", tool_calls=None, role="assistant"))],
        usage=None,
    )
    llm._client = client
    with bind_current_node("n1", "tekos"):
        llm.chat([ChatMessage(role=Role.USER, content="hi")])

    headers = client.chat.completions.create.call_args.kwargs["extra_headers"]
    assert headers == {"X-Zuno-Agent": "tekos", "Authorization": "Bearer user-tok"}


def test_openai_compatible_without_forwarding_sends_no_extra_headers():
    from mas.elements.llms.openai_compatible.openai_compatible import (
        OpenAICompatibleLLM,
    )
    llm = OpenAICompatibleLLM(base_url="http://gw/v1", model_name="m")
    assert llm._request_options() == {}


def test_mcp_forward_mode_binds_forwarded_credential_and_no_static_headers():
    from mas.core.element_deps import ElementBuildContext
    from mas.elements.providers.mcp_server_client.config import (
        McpAuthMethod,
        McpProviderConfig,
    )
    from mas.elements.providers.mcp_server_client.mcp_provider_factory import (
        McpProviderFactory,
    )
    from mas.session.building.category_builders.provider_builder import ProviderBuilder

    cfg = McpProviderConfig(
        mcp_url="http://mcp-gateway/mcp",
        auth_method=McpAuthMethod.FORWARD_USER_TOKEN,
        additional_headers={"X-Zuno-Agent": "{node_name}"},
    )
    deps = ElementBuildContext(execution_ctx=_holder(), identity_token_source=StaticSource("u"))
    extra = ProviderBuilder(MagicMock())._extra_kwargs(cfg, MagicMock(), deps=deps)
    cred = extra["auth_credential"]
    assert isinstance(cred, ForwardedIdentityCredential)
    with bind_current_node("n", "tekos"):
        assert asyncio.run(cred.get_headers()) == {"X-Zuno-Agent": "tekos", "Authorization": "Bearer u"}
    assert McpProviderFactory()._build_headers(cfg) is None


# ── validator ────────────────────────────────────────────────────────────────

def _validate(cfg, monkeypatch, *, get=None):
    import httpx
    from mas.elements.common.validator import ValidationContext
    from mas.elements.llms.openai_compatible import validator as mod

    calls = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            calls.append(url)
            if get is not None:
                return get(url)
            return httpx.Response(401, request=httpx.Request("GET", url))

    monkeypatch.setattr(mod.httpx, "Client", FakeClient)
    probed = MagicMock(side_effect=AssertionError("the model must not be probed"))
    monkeypatch.setattr(mod, "OpenAI", probed)
    report = mod.OpenAICompatibleLLMValidator().validate(cfg, ValidationContext())
    return report, calls


def test_validator_does_not_probe_the_model_when_forwarding(monkeypatch):
    from mas.elements.llms.openai_compatible.config import OpenAICompatibleConfig

    cfg = OpenAICompatibleConfig(model_name="auto", base_url="http://gw:8080/v1/", forward_user_token=True)
    report, calls = _validate(cfg, monkeypatch)
    assert calls == ["http://gw:8080/v1/models"]
    assert [m.code for m in report.messages] == ["MODEL_CHECK_SKIPPED"]
    assert all(m.severity.value != "error" for m in report.messages)


def test_validator_reports_an_unreachable_forwarding_endpoint(monkeypatch):
    import httpx
    from mas.elements.llms.openai_compatible.config import OpenAICompatibleConfig

    def refuse(url):
        raise httpx.ConnectError("refused", request=httpx.Request("GET", url))

    cfg = OpenAICompatibleConfig(model_name="auto", base_url="http://gw:8080/v1", forward_user_token=True)
    report, _ = _validate(cfg, monkeypatch, get=refuse)
    assert [m.severity.value for m in report.messages] == ["error"]


# ── MCP validator ────────────────────────────────────────────────────────────

def _validate_mcp(cfg, monkeypatch, *, get=None):
    import httpx
    from mas.elements.common.validator import ValidationContext
    from mas.elements.providers.mcp_server_client import validator as mod

    calls = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            calls.append(url)
            if get is not None:
                return get(url)
            return httpx.Response(401, request=httpx.Request("GET", url))

    monkeypatch.setattr(mod.httpx, "Client", FakeClient)
    factory = MagicMock()
    factory.create_async.side_effect = AssertionError("no MCP handshake without the user's token")
    report = mod.McpProviderValidator(factory=factory).validate(cfg, ValidationContext())
    return report, calls


def test_mcp_validator_does_not_handshake_when_forwarding(monkeypatch):
    from mas.elements.providers.mcp_server_client.config import McpProviderConfig

    cfg = McpProviderConfig(
        mcp_url="http://mcp-gateway:8080/mcp", transport_type="streamable http", auth_method="forward_user_token",
    )
    report, calls = _validate_mcp(cfg, monkeypatch)
    assert calls == ["http://mcp-gateway:8080/mcp"]
    assert [m.code for m in report.messages] == ["CONNECTION_CHECK_SKIPPED"]
    assert all(m.severity.value != "error" for m in report.messages)


def test_mcp_validator_reports_an_unreachable_forwarding_endpoint(monkeypatch):
    import httpx
    from mas.elements.providers.mcp_server_client.config import McpProviderConfig

    def refuse(url):
        raise httpx.ConnectError("refused", request=httpx.Request("GET", url))

    cfg = McpProviderConfig(
        mcp_url="http://mcp-gateway:8080/mcp", transport_type="streamable http", auth_method="forward_user_token",
    )
    report, _ = _validate_mcp(cfg, monkeypatch, get=refuse)
    assert [m.severity.value for m in report.messages] == ["error"]
