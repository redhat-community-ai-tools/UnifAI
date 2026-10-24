"""A stored credential, or the user's platform token, is presented only to the URL it is meant for."""
import asyncio

import pytest

from mas.core.auth.credentials.models import StoredCredential, TokenSet
from mas.core.auth.errors import CredentialTargetError
from mas.core.auth.ports import CompletionResult
from mas.core.auth.service import AuthService
from mas.core.auth.target_policy import credential_may_be_sent, forwarding_target_allowed, origin_of
from mas.core.identity_forwarding import (
    ForwardedIdentityCredential, IdentityForwarder, IdentityTokenUnavailable, NullIdentityTokenSource,
)

ISSUER = "https://auth.example.com/realms/x"
MCP = "https://mcp.example.com/mcp"


class MemoryStore:
    def __init__(self):
        self.rows = {}

    def upsert(self, c):
        self.rows[(c.user_id, c.server_identifier.rstrip("/"))] = c

    def find_by_server(self, user_id, server_identifier, scheme_type=""):
        return self.rows.get((user_id, server_identifier.rstrip("/")))

    def delete(self, user_id, server_identifier):
        self.rows.pop((user_id, server_identifier.rstrip("/")), None)

    def update_status(self, *a, **k):
        pass


class FakeStrategy:
    def __init__(self, resource_origin=""):
        self.resource_origin = resource_origin

    async def complete(self, raw):
        return CompletionResult(
            token_set=TokenSet(access_token="tok"), user_id="alice", server_identifier=ISSUER,
            scheme_type="oauth2", resource_origin=self.resource_origin,
        )

    def build_headers(self, cred):
        return {"Authorization": f"Bearer {cred.access_token}"}


class Registry:
    def __init__(self, strategy):
        self._s = strategy

    def get(self, scheme):
        return self._s


def _service(store=None, strategy=None):
    return AuthService(store or MemoryStore(), Registry(strategy or FakeStrategy()))


# ── pure policy ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url,expected", [
    ("https://MCP.example.com:8443/a/b?q=1", "https://mcp.example.com:8443"),
    ("http://svc.ns.svc:8080/mcp", "http://svc.ns.svc:8080"),
    ("https://user:pw@evil.example/", ""),
    ("ftp://x.example/", ""),
    ("not a url", ""),
    ("", ""),
])
def test_origin_of(url, expected):
    assert origin_of(url) == expected


def test_recorded_origins_win_over_the_issuer():
    assert credential_may_be_sent(ISSUER, ["https://mcp.example.com"], MCP)
    assert not credential_may_be_sent(ISSUER, ["https://mcp.example.com"], "https://evil.example/mcp")
    assert not credential_may_be_sent(ISSUER, ["https://mcp.example.com"], ISSUER)


def test_without_recorded_origins_only_the_issuer_origin_is_allowed():
    assert credential_may_be_sent("https://api.example.com/", [], "https://api.example.com/v1/mcp")
    assert not credential_may_be_sent(ISSUER, [], "https://evil.example/mcp")
    assert not credential_may_be_sent(ISSUER, [], "")


@pytest.mark.parametrize("url", [
    "http://mcp-gateway.zuno-ai-run.svc:8080/mcp",
    "http://mcp-gateway.zuno-ai-run.svc.cluster.local/mcp",
    "http://mcp-gateway:8080/mcp",
])
def test_user_token_goes_to_cluster_internal_services(url):
    assert forwarding_target_allowed(url, allowed_hosts=[])


@pytest.mark.parametrize("url", [
    "https://evil.example/mcp", "http://169.254.169.254/latest", "http://localhost:8080/", "", "http://svc.ns.svc.evil.example/",
])
def test_user_token_is_refused_elsewhere(url):
    assert not forwarding_target_allowed(url, allowed_hosts=[])


def test_user_token_allow_list_is_exact_host():
    assert forwarding_target_allowed("https://gw.corp.example/mcp", allowed_hosts=["gw.corp.example"])
    assert not forwarding_target_allowed("https://other.corp.example/mcp", allowed_hosts=["gw.corp.example"])


# ── service ──────────────────────────────────────────────────────────────────

def test_sign_in_records_the_resource_origin_and_bind_honours_it():
    svc = _service(strategy=FakeStrategy(resource_origin="https://mcp.example.com"))
    asyncio.run(svc.complete({"scheme_type": "oauth2"}))
    assert svc.bind("alice", ISSUER, target_url=MCP) is not None
    assert svc.bind("alice", ISSUER, target_url="https://evil.example/mcp") is None


def test_second_sign_in_for_another_resource_adds_its_origin():
    store = MemoryStore()
    asyncio.run(_service(store, FakeStrategy("https://mcp.example.com")).complete({}))
    asyncio.run(_service(store, FakeStrategy("https://mcp2.example.com")).complete({}))
    assert store.rows[("alice", ISSUER)].resource_origins == ["https://mcp.example.com", "https://mcp2.example.com"]


def test_legacy_credential_is_not_sent_to_a_foreign_host():
    store = MemoryStore()
    store.upsert(StoredCredential(user_id="alice", server_identifier=ISSUER, access_token="tok"))
    svc = _service(store)
    assert svc.bind("alice", ISSUER, target_url="https://evil.example/mcp") is None
    assert svc.bind("alice", ISSUER, target_url=ISSUER + "/mcp") is not None


def test_bind_without_a_target_keeps_working_for_non_url_callers():
    store = MemoryStore()
    store.upsert(StoredCredential(user_id="alice", server_identifier=ISSUER, access_token="tok"))
    assert _service(store).bind("alice", ISSUER) is not None


def test_lazy_handle_fails_closed_for_a_foreign_target():
    store = MemoryStore()
    store.upsert(StoredCredential(
        user_id="alice", server_identifier=ISSUER, access_token="tok", resource_origins=["https://mcp.example.com"],
    ))
    svc = _service(store)
    good = svc.bind_lazy(lambda: "alice", ISSUER, target_url=MCP)
    bad = svc.bind_lazy(lambda: "alice", ISSUER, target_url="https://evil.example/mcp")
    assert asyncio.run(good.get_headers()) == {"Authorization": "Bearer tok"}
    with pytest.raises(CredentialTargetError):
        asyncio.run(bad.get_headers())
    with pytest.raises(CredentialTargetError):
        asyncio.run(bad.get_token())


def test_another_users_credential_is_never_used_for_the_handle():
    store = MemoryStore()
    store.upsert(StoredCredential(user_id="alice", server_identifier=ISSUER, access_token="tok", resource_origins=[MCP]))
    handle = _service(store).bind_lazy(lambda: "bob", ISSUER, target_url=MCP)
    with pytest.raises(CredentialTargetError):
        asyncio.run(handle.get_headers())


# ── forwarded platform token ─────────────────────────────────────────────────

def test_forwarded_token_is_refused_for_an_external_target():
    cred = ForwardedIdentityCredential(IdentityForwarder(NullIdentityTokenSource(), None), {}, target_url="https://evil.example/mcp")
    with pytest.raises(IdentityTokenUnavailable, match="cluster-internal"):
        asyncio.run(cred.get_headers())
    with pytest.raises(IdentityTokenUnavailable, match="cluster-internal"):
        asyncio.run(cred.get_token())


def test_forwarded_token_without_any_target_is_refused():
    cred = ForwardedIdentityCredential(IdentityForwarder(NullIdentityTokenSource(), None), {})
    with pytest.raises(IdentityTokenUnavailable, match="cluster-internal"):
        asyncio.run(cred.get_token())


# ── LLM endpoint forwarding ──────────────────────────────────────────────────

def test_forwarder_refuses_the_token_for_an_external_model_endpoint():
    fw = IdentityForwarder(NullIdentityTokenSource(), None, target_urls=("https://evil.example/v1",))
    with pytest.raises(IdentityTokenUnavailable, match="cluster-internal"):
        fw.access_token()


def test_forwarder_checks_every_target_including_the_routing_lookup():
    fw = IdentityForwarder(
        NullIdentityTokenSource(), None,
        target_urls=("http://ai-gateway.zuno-ai-run.svc:8080/v1", "https://evil.example/{request_id}"),
    )
    with pytest.raises(IdentityTokenUnavailable, match="cluster-internal"):
        fw.access_token()


def test_forwarder_without_targets_keeps_its_old_behaviour():
    with pytest.raises(IdentityTokenUnavailable, match="no execution context"):
        IdentityForwarder(NullIdentityTokenSource(), None).access_token()
