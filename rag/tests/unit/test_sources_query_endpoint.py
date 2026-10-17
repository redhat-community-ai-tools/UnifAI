"""/api/sources/query.match searches the collection of the requested source type."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g

pytestmark = pytest.mark.unit


@pytest.fixture
def client():
    from infrastructure.http import auth, sources

    def fake_session(f):
        def wrapped(*a, **kw):
            g.user_id = "alice"
            g.identity_session = SimpleNamespace(access_token=None)
            return f(*a, **kw)
        wrapped.__name__ = f.__name__
        return wrapped

    with patch.object(auth, "rag_require_session", fake_session):
        import importlib
        importlib.reload(sources)
        app = Flask(__name__)
        app.register_blueprint(sources.sources_bp, url_prefix="/api/sources/")
        yield app.test_client(), sources
    importlib.reload(sources)


def test_unknown_source_type_is_refused(client):
    c, _ = client
    assert c.get("/api/sources/query.match?query=q&sourceType=PASSWORDS").status_code == 400


def test_confluence_search_uses_the_confluence_collection_and_caller_scope(client):
    c, sources = client
    svc = MagicMock()
    svc.search.return_value = [{"id": "1", "score": 0.03, "content": "x", "metadata": {}}]
    with patch.object(sources, "retrieval_service", return_value=svc) as rs, \
         patch.object(sources, "caller_groups", return_value=["agent_tekos"]), \
         patch.object(sources.AppConfig, "get_instance", return_value=SimpleNamespace(oidc_issuer_url="", oidc_verify_tls=True)):
        resp = c.get("/api/sources/query.match?query=satellite&sourceType=confluence&top_k_results=3")
    assert resp.status_code == 200 and resp.get_json()["matches"][0]["id"] == "1"
    rs.assert_called_once_with("CONFLUENCE")
    kwargs = svc.search.call_args.kwargs
    assert kwargs["owner_id"] == "alice" and kwargs["caller_groups"] == ["agent_tekos"] and kwargs["limit"] == 3
