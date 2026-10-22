"""Shared sources: owner + ACL-group visibility, fail closed everywhere."""
import base64
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
import pytest
import qdrant_client
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask, g

from core.pipeline.executor import PipelineExecutor
from core.vector.domain.model import AccessScope, VectorChunk
from infrastructure.http import caller_groups as cg
from infrastructure.qdrant.qdrant_vector_repository import QdrantVectorRepository
from infrastructure.retrieval.source_filter_resolver import SourceFilterResolver

pytestmark = pytest.mark.unit


def _point(source, owner, visibility="private", groups=(), emb=(1.0, 0.0)):
    return VectorChunk(text=f"text of {source}", embedding=list(emb),
                       metadata={"source_id": source, "chunk_index": 0, "owner_id": owner,
                                 "visibility": visibility, "acl_groups": list(groups)})


@pytest.fixture
def repo():
    r = QdrantVectorRepository(collection_name="acl", embedding_dim=2, url="http://unused", hybrid=True,
                               client=qdrant_client.QdrantClient(":memory:"))
    r.initialize()
    r.store([
        _point("alice-private", "alice"),
        _point("bob-private", "bob"),
        _point("tech-corpus", "operator", "shared", ["agent_tekos", "consultants"]),
        _point("finance-corpus", "operator", "shared", ["finance"]),
        _point("shared-to-nobody", "operator", "shared", []),
    ])
    return r


def _visible(repo, owner, groups=()):
    hits = repo.search([1.0, 0.0], top_k=10, query_text="text", access=AccessScope(owner, frozenset(groups)))
    return {h.metadata["source_id"] for h in hits}


def test_owner_sees_only_own_sources_without_groups(repo):
    assert _visible(repo, "alice") == {"alice-private"}


def test_group_member_also_sees_matching_shared_sources(repo):
    assert _visible(repo, "alice", ["consultants"]) == {"alice-private", "tech-corpus"}
    assert _visible(repo, "bob", ["finance", "agent_tekos"]) == {"bob-private", "tech-corpus", "finance-corpus"}


def test_shared_source_without_groups_is_visible_to_nobody_else(repo):
    assert "shared-to-nobody" not in _visible(repo, "alice", ["consultants", "finance"])
    assert "shared-to-nobody" in _visible(repo, "operator")


# ── registration policy ──────────────────────────────────────────────────────

def _registration(upload_by, instance, publishers=frozenset()):
    from core.registration.base_registration import BaseRegistration

    class Probe(BaseRegistration):
        DATA_SOURCE_TYPE = "PROBE"
        source_data = SimpleNamespace(source_id="s1", source_name="probe", pipeline_id="probe_s1", form_data=None)

        def _build_metadata(self):
            return {}

        def _build_type_data(self):
            return {}

        def run_validator(self):
            return True, None

    repo = MagicMock()
    reg = Probe(repo, upload_by, instance)
    reg._shared_publishers = publishers
    return reg, repo


def test_shared_registration_is_refused_for_non_publishers():
    reg, repo = _registration("mallory", {"visibility": "shared", "aclGroups": ["agent_tekos"]})
    source, issue = reg.register()
    assert source is None and issue["error_type"] == "ACCESS_DENIED"
    repo.save.assert_not_called()


def test_publisher_registers_a_shared_source_with_normalised_groups():
    reg, repo = _registration("operator", {"visibility": "shared", "aclGroups": ["/agent_tekos", "consultants", ""]},
                              publishers=frozenset({"operator"}))
    _source, issue = reg.register()
    assert issue is None
    saved = repo.save.call_args.args[0]
    assert saved.visibility == "shared" and saved.acl_groups == ["agent_tekos", "consultants"]


def test_default_registration_stays_private():
    reg, repo = _registration("alice", {})
    reg.register()
    assert repo.save.call_args.args[0].visibility == "private"


# ── pipeline stamping ────────────────────────────────────────────────────────

def test_executor_stamps_source_access_on_every_chunk():
    svc = MagicMock()
    svc.get_by_id.return_value = SimpleNamespace(visibility="shared", acl_groups=["agent_tekos"])
    ex = PipelineExecutor.__new__(PipelineExecutor)
    ex._data_source_svc = svc
    chunks = [VectorChunk(text="a", embedding=[1.0], metadata={"chunk_index": 0})]
    ex._stamp_access("s1", chunks)
    assert chunks[0].metadata["visibility"] == "shared" and chunks[0].metadata["acl_groups"] == ["agent_tekos"]


def test_executor_falls_back_to_private_when_the_source_is_unreadable():
    svc = MagicMock()
    svc.get_by_id.side_effect = RuntimeError("mongo down")
    ex = PipelineExecutor.__new__(PipelineExecutor)
    ex._data_source_svc = svc
    chunks = [VectorChunk(text="a", embedding=[1.0], metadata={})]
    ex._stamp_access("s1", chunks)
    assert chunks[0].metadata["visibility"] == "private" and chunks[0].metadata["acl_groups"] == []


# ── source filter resolver ───────────────────────────────────────────────────

def test_resolver_includes_shared_sources_of_the_callers_groups():
    col = MagicMock()
    col.find.return_value = [{"source_id": "tech-corpus"}]
    SourceFilterResolver(col).resolve("DOCUMENT", "alice", tags=["tech"], caller_groups={"consultants"})
    query = col.find.call_args.args[0]
    visible = query["$and"][0]["$or"]
    assert {"upload_by": "alice"} in visible
    assert {"visibility": "shared", "acl_groups": {"$in": ["consultants"]}} in visible


def test_resolver_without_groups_only_matches_own_sources():
    col = MagicMock()
    col.find.return_value = []
    SourceFilterResolver(col).resolve("DOCUMENT", "alice", doc_ids=["d1"])
    assert col.find.call_args.args[0]["$and"][0]["$or"] == [{"upload_by": "alice"}]


# ── caller groups ────────────────────────────────────────────────────────────

ISSUER = "https://keycloak.example/realms/zuno"


def _b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")


@pytest.fixture
def app():
    return Flask(__name__)


def test_browser_session_token_groups_are_used(app):
    token = f"{_b64({'alg': 'none'})}.{_b64({'groups': ['/agent_tekos', 'consultants']})}.sig"
    with app.test_request_context("/"):
        g.identity_session = SimpleNamespace(access_token=token)
        g.user_id = "alice"
        assert cg.caller_groups(ISSUER) == ["agent_tekos", "consultants"]


def _signed(key, **claims):
    body = {"iss": ISSUER, "exp": int(time.time()) + 60, **claims}
    return jwt.encode(body, key, algorithm="RS256", headers={"kid": "k1"})


def _verify_with(key):
    jwk = MagicMock()
    jwk.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key.public_key())
    return patch.object(cg, "_jwks_client", return_value=jwk)


def test_forwarded_token_is_verified_and_bound_to_the_request_user(app):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _signed(key, preferred_username="alice", groups=["/agent_tekos"])
    with _verify_with(key), app.test_request_context("/", headers={"Authorization": f"Bearer {token}"}):
        g.identity_session = SimpleNamespace(access_token=None)
        g.user_id = "alice"
        assert cg.caller_groups(ISSUER) == ["agent_tekos"]
        g.user_id = "bob"
        assert cg.caller_groups(ISSUER) == []


def test_forwarded_token_of_a_team_member_is_accepted_for_the_team_workspace(app):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _signed(key, preferred_username="alice", groups=["/agent_tekos"])
    client = MagicMock()
    client.is_member.side_effect = lambda user, team: (user, team) == ("alice", "team-1")
    with _verify_with(key), patch("bootstrap.app_container.identity_client", return_value=client), \
            app.test_request_context("/", headers={"Authorization": f"Bearer {token}"}):
        g.identity_session = SimpleNamespace(access_token=None)
        g.user_id = "team-1"
        assert cg.caller_groups(ISSUER) == ["agent_tekos"]
        g.user_id = "team-2"
        assert cg.caller_groups(ISSUER) == []


def test_membership_lookup_failure_yields_no_group(app):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _signed(key, preferred_username="alice", groups=["/agent_tekos"])
    client = MagicMock()
    client.is_member.side_effect = RuntimeError("identity down")
    with _verify_with(key), patch("bootstrap.app_container.identity_client", return_value=client), \
            app.test_request_context("/", headers={"Authorization": f"Bearer {token}"}):
        g.identity_session = SimpleNamespace(access_token=None)
        g.user_id = "team-1"
        assert cg.caller_groups(ISSUER) == []


def test_forged_or_expired_tokens_yield_no_group(app):
    key, other = (rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2))
    forged = _signed(other, preferred_username="alice", groups=["finance"])
    expired = jwt.encode({"iss": ISSUER, "exp": int(time.time()) - 10, "preferred_username": "alice", "groups": ["x"]},
                         key, algorithm="RS256")
    for token in (forged, expired):
        with _verify_with(key), app.test_request_context("/", headers={"Authorization": f"Bearer {token}"}):
            g.identity_session = SimpleNamespace(access_token=None)
            g.user_id = "alice"
            assert cg.caller_groups(ISSUER) == []


def test_no_issuer_configured_ignores_bearer_tokens(app):
    with app.test_request_context("/", headers={"Authorization": "Bearer anything"}):
        g.identity_session = SimpleNamespace(access_token=None)
        g.user_id = "alice"
        assert cg.caller_groups("") == []
