"""/api/sources/query.bearer: a service holding only the user's token can search, as that user."""
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask

pytestmark = pytest.mark.unit

ISSUER = "https://keycloak.example/realms/zuno"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def cfg(**kw):
    base = dict(oidc_issuer_url=ISSUER, oidc_verify_tls=True, rag_bearer_audience="zuno-admin-api",
                rag_tokenreview_enabled=False)
    base.update(kw)
    return SimpleNamespace(**base)


def token(**claims):
    payload = {"iss": ISSUER, "aud": ["zuno-admin-api", "tekos-frontend"], "preferred_username": "consultant-01",
               "groups": ["/consultant/confluence-build-satellite", "/agent_tekos"], "exp": int(time.time()) + 300}
    payload.update(claims)
    return jwt.encode(payload, KEY, algorithm="RS256")


@pytest.fixture
def bearer():
    from infrastructure.http import bearer_auth

    jwks = MagicMock()
    jwks.get_signing_key_from_jwt.return_value = SimpleNamespace(key=KEY.public_key())
    with patch.object(bearer_auth, "_jwks_client", return_value=jwks):
        yield bearer_auth


def test_a_keycloak_token_gives_the_user_and_the_normalised_groups(bearer):
    caller = bearer.authenticate_bearer(token(), cfg())
    assert caller.username == "consultant-01"
    assert caller.groups == ["agent_tekos", "consultant/confluence-build-satellite"]


def test_the_audience_must_be_the_expected_one(bearer):
    assert bearer.authenticate_bearer(token(aud=["tekos-frontend"]), cfg()) is None
    assert bearer.authenticate_bearer(token(aud=["tekos-frontend"]), cfg(rag_bearer_audience="")) is not None


def test_an_expired_token_is_refused(bearer):
    assert bearer.authenticate_bearer(token(exp=int(time.time()) - 10), cfg()) is None


def test_another_issuer_is_not_trusted_and_gets_no_token_review_when_off(bearer):
    assert bearer.authenticate_bearer(token(iss="https://evil.example/realms/zuno"), cfg()) is None


def test_a_token_signed_with_another_key_is_refused(bearer):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode({"iss": ISSUER, "aud": "zuno-admin-api", "preferred_username": "boss", "exp": int(time.time()) + 60},
                        other, algorithm="RS256")
    assert bearer.authenticate_bearer(forged, cfg()) is None


def test_a_token_without_a_user_is_refused(bearer):
    assert bearer.authenticate_bearer(token(preferred_username=None), cfg()) is None


def _review(status):
    resp = MagicMock()
    resp.json.return_value = {"status": status}
    return resp


def test_an_opaque_token_is_refused_unless_token_review_is_enabled(bearer):
    with patch.object(bearer.requests, "post") as post:
        assert bearer.authenticate_bearer("sha256~opaque", cfg()) is None
        post.assert_not_called()


def test_an_opaque_token_goes_through_token_review_when_enabled(bearer, tmp_path):
    (tmp_path / "token").write_text("sa-token")
    status = {"authenticated": True, "user": {"username": "ai-ops-01", "groups": ["ocp-ai-ops", "system:authenticated"]}}
    with patch.object(bearer, "_SA_DIR", str(tmp_path)), patch.object(bearer.requests, "post", return_value=_review(status)) as post:
        caller = bearer.authenticate_bearer("sha256~opaque", cfg(rag_tokenreview_enabled=True))
    assert caller.username == "ai-ops-01" and caller.groups == ["ocp-ai-ops"]
    assert post.call_args.kwargs["json"]["spec"]["token"] == "sha256~opaque"


@pytest.mark.parametrize("status", [
    {"authenticated": False},
    {"authenticated": True, "user": {"username": "system:serviceaccount:ns:sa", "groups": []}},
    {"authenticated": True, "user": {}},
])
def test_token_review_refuses_unauthenticated_and_system_identities(bearer, tmp_path, status):
    (tmp_path / "token").write_text("sa-token")
    with patch.object(bearer, "_SA_DIR", str(tmp_path)), patch.object(bearer.requests, "post", return_value=_review(status)):
        assert bearer.authenticate_bearer("sha256~opaque", cfg(rag_tokenreview_enabled=True)) is None


def test_a_token_review_failure_is_a_refusal_not_an_error(bearer, tmp_path):
    (tmp_path / "token").write_text("sa-token")
    with patch.object(bearer, "_SA_DIR", str(tmp_path)), \
            patch.object(bearer.requests, "post", side_effect=bearer.requests.ConnectionError("down")):
        assert bearer.authenticate_bearer("sha256~opaque", cfg(rag_tokenreview_enabled=True)) is None


@pytest.fixture
def client(bearer):
    from infrastructure.http import sources

    app = Flask(__name__)
    app.register_blueprint(sources.sources_bp, url_prefix="/api/sources/")
    with patch.object(bearer.AppConfig, "get_instance", return_value=cfg()):
        yield app.test_client(), sources


def test_the_endpoint_needs_a_bearer_and_ignores_cookies_and_internal_headers(client):
    c, _ = client
    resp = c.get("/api/sources/query.bearer?query=q&sourceType=CONFLUENCE",
                 headers={"X-Authenticated-User": "boss", "X-Internal-Auth": "secret", "Cookie": "session=abc"})
    assert resp.status_code == 401


def test_the_endpoint_rejects_a_bad_token(client):
    c, _ = client
    resp = c.get("/api/sources/query.bearer?query=q&sourceType=CONFLUENCE", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_the_endpoint_searches_as_the_token_user_with_the_token_groups(client):
    c, sources = client
    svc = MagicMock()
    svc.search.return_value = [{"id": "1", "score": 0.4, "content": "x", "metadata": {}}]
    with patch.object(sources, "retrieval_service", return_value=svc) as rs:
        resp = c.get("/api/sources/query.bearer?query=satellite&sourceType=confluence&tags=knowledge.tech&top_k_results=4",
                     headers={"Authorization": f"Bearer {token()}", "X-Authenticated-User": "boss"})
    assert resp.status_code == 200 and resp.get_json()["matches"][0]["id"] == "1"
    rs.assert_called_once_with("CONFLUENCE")
    kw = svc.search.call_args.kwargs
    assert kw["owner_id"] == "consultant-01"
    assert kw["caller_groups"] == ["agent_tekos", "consultant/confluence-build-satellite"]
    assert kw["tags"] == ["knowledge.tech"] and kw["limit"] == 4


def test_the_endpoint_refuses_an_unknown_source_type(client):
    c, _ = client
    resp = c.get("/api/sources/query.bearer?query=q&sourceType=PASSWORDS", headers={"Authorization": f"Bearer {token()}"})
    assert resp.status_code == 400
