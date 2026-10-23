"""Web source: link discovery, conditional fetching, incremental sync, idempotent registration."""
import socket
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from core.data_sources.domain.model import DataSource
from core.data_sources.types.web.pipeline_handler import (
    WebPipelineHandler,
    page_id,
    page_title,
)
from core.data_sources.types.web.registration import WebRegistration
from core.pipeline.domain.port import PipelineContext
from infrastructure.sources.web.connector import (
    WebConnector,
    WebError,
    discover_links,
    in_scope,
    resolve_public,
)

pytestmark = pytest.mark.unit

SEED = "https://docs.example.com/en/documentation/product/1.0/html/guide/index"
LANDING = (
    '<html><head><title>Guide</title></head><body><nav><a href="/en/other">nav</a></nav>'
    '<a href="/en/documentation/product/1.0/html/guide/chapter-1">c1</a>'
    '<a href="/en/documentation/product/1.0/html-single/guide/index#top">single</a>'
    '<a href="/en/documentation/product/1.0/html/guide/chapter-1#x">dup</a>'
    '<a href="/en/support/index">support</a><a href="https://elsewhere.org/html/x">ext</a>'
    '<a href="mailto:a@b.c">mail</a></body></html>'
)
C1 = "https://docs.example.com/en/documentation/product/1.0/html/guide/chapter-1"
SINGLE = "https://docs.example.com/en/documentation/product/1.0/html-single/guide/index"


def test_discovery_keeps_book_links_of_the_same_host_without_duplicates_or_fragments():
    assert discover_links(SEED, LANDING, "redhat-docs", 50) == [C1, SINGLE]


def test_generic_discovery_stays_under_the_seed_directory():
    html = '<a href="chapter">a</a><a href="/elsewhere">b</a>'
    assert discover_links("https://x.org/docs/index.html", html, "generic", 50) == ["https://x.org/docs/chapter"]


def test_no_crawl_and_cap():
    assert discover_links(SEED, LANDING, "none", 50) == []
    assert discover_links(SEED, LANDING, "redhat-docs", 1) == [C1]


def test_include_and_exclude_patterns():
    assert in_scope(C1, ["*/chapter-*"], []) and not in_scope(C1, ["*/other-*"], [])
    assert not in_scope(C1, [], ["*chapter-1"])


def test_title_comes_from_h1_then_title():
    assert page_title("<h1> The  <b>H1</b> </h1>", "u") == "The H1"
    assert page_title("<html><title>Only title</title>", "u") == "Only title"
    assert page_title("<p>none</p>", "https://u") == "https://u"


# ── connector ────────────────────────────────────────────────────────────────

def _session(site, calls):
    """site: {url: (status, body, headers)}; calls records (url, conditional headers)."""
    session = MagicMock()
    session.headers = {}

    def get(url, headers=None, timeout=None, allow_redirects=True):
        assert allow_redirects is False
        calls.append((url, dict(headers or {})))
        status, body, hdrs = site[url]
        return SimpleNamespace(status_code=status, text=body, content=body.encode(), headers=hdrs)

    session.get.side_effect = get
    return session


def _connector(site, calls):
    return WebConnector(session=_session(site, calls), min_interval=0, sleep=lambda _s: None,
                        host_check=lambda _h: None)


def test_connector_fetches_the_seed_unconditionally_and_the_rest_conditionally():
    site = {SEED: (200, LANDING, {}), C1: (304, "", {}), SINGLE: (200, "<h1>S</h1><p>x</p>", {"ETag": '"e2"'})}
    calls = []
    previous = {C1: {"etag": '"e1"', "last_modified": "Mon, 01 Jan 2026 00:00:00 GMT"}}
    out = dict(_connector(site, calls).iter_pages([SEED], previous))
    assert out[SEED].html == LANDING and out[C1] is None and out[SINGLE].etag == '"e2"'
    assert calls[0] == (SEED, {})
    assert dict(calls)[C1] == {"If-None-Match": '"e1"', "If-Modified-Since": "Mon, 01 Jan 2026 00:00:00 GMT"}


def test_connector_survives_an_unreadable_page():
    site = {SEED: (200, LANDING, {}), C1: (503, "", {}), SINGLE: (200, "<p>ok</p>", {})}
    out = dict(_connector(site, []).iter_pages([SEED], {}))
    assert out[C1] is None and out[SINGLE] is not None


def test_redirects_are_followed_with_the_host_check_on_each_hop():
    site = {SEED: (302, "", {"Location": "/en/final"}), "https://docs.example.com/en/final": (200, "<p>ok</p>", {})}
    seen = []
    conn = WebConnector(session=_session(site, []), min_interval=0, sleep=lambda _s: None, host_check=seen.append)
    assert conn.fetch(SEED).html == "<p>ok</p>" and seen == ["docs.example.com", "docs.example.com"]


def test_a_redirect_to_an_internal_host_is_refused():
    site = {SEED: (302, "", {"Location": "http://169.254.169.254/latest/meta-data"})}
    def check(host):
        if host == "169.254.169.254":
            raise WebError(f"{host} resolves to a non-public address")

    conn = WebConnector(session=_session(site, []), min_interval=0, sleep=lambda _s: None, host_check=check)
    with pytest.raises(WebError, match="non-public"):
        conn.fetch(SEED)


@pytest.mark.parametrize("host", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "172.30.0.1", "::1", "192.168.1.1"])
def test_non_public_addresses_are_refused(host, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", (host, 0))])
    with pytest.raises(WebError, match="non-public"):
        resolve_public("whatever.example.com")


def test_public_address_is_accepted(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("23.220.75.245", 0))])
    resolve_public("docs.redhat.com")


def test_allowed_hosts_restrict_sources_to_listed_domains():
    conn = WebConnector(session=_session({}, []), allowed_hosts=["redhat.com"], host_check=lambda _h: None)
    conn._check("https://docs.redhat.com/x")
    for bad in ("https://evil.com/x", "https://notredhat.com/x", "file:///etc/passwd"):
        with pytest.raises(WebError):
            conn._check(bad)


# ── pipeline handler ─────────────────────────────────────────────────────────

CTX = PipelineContext(pipeline_id="p", source_type="WEB", source_id="s1", source_name="web", owner_id="operator",
                      metadata={})


class _Chunker:
    def chunk_content(self, docs):
        return [{"text": docs[0]["content"]}]


class _Embedder:
    def generate_embeddings(self, chunks):
        return [{**c, "embedding": np.zeros(2)} for c in chunks]


def _web_page(url, body="<p>text</p>", etag=""):
    import hashlib
    return SimpleNamespace(url=url, html=body, content_hash=hashlib.sha256(body.encode()).hexdigest(),
                           etag=etag, last_modified="")


def _handler(manifest, iterated, metadata=None):
    connector = MagicMock()
    connector.iter_pages.return_value = iter(iterated)
    sources = MagicMock()
    sources.get_by_id.return_value = SimpleNamespace(type_data={
        "urls": [SEED], "pages": manifest, "metadata": metadata or {"product": "Product", "version": "1.0"}})
    return WebPipelineHandler(lambda: connector, _Chunker(), _Embedder(), sources)


def _run(handler):
    collected = handler.collect(CTX)
    chunks = handler.chunk_and_embed(CTX, handler.process(CTX, collected))
    return chunks, handler.stale_point_filters(CTX), handler.get_summary(CTX, collected)


def test_first_run_embeds_every_page_with_the_source_metadata():
    chunks, stale, summary = _run(_handler({}, [(SEED, _web_page(SEED)), (C1, _web_page(C1, "<h1>One</h1><p>a</p>"))]))
    assert {c.metadata["url"] for c in chunks} == {SEED, C1}
    assert all(c.metadata["product"] == "Product" and c.metadata["version"] == "1.0" for c in chunks)
    assert stale[0]["metadata.page_id"] == [page_id(SEED), page_id(C1)]
    assert summary["pages"][C1]["title"] == "One"


def test_unchanged_pages_embed_nothing():
    first = _handler({}, [(SEED, _web_page(SEED)), (C1, _web_page(C1))])
    _run(first)
    manifest = first.get_summary(CTX, None)["pages"]
    chunks, stale, summary = _run(_handler(manifest, [(SEED, _web_page(SEED)), (C1, None)]))
    assert chunks == [] and stale == [] and summary["pages_unchanged"] == 2 and summary["page_count"] == 2


def test_changed_page_alone_is_replaced_and_vanished_page_removed():
    old = {SEED: {"content_hash": _web_page(SEED).content_hash, "title": "t"},
           C1: {"content_hash": "old", "title": "t"}, SINGLE: {"content_hash": "x", "title": "t"}}
    chunks, stale, summary = _run(_handler(old, [(SEED, _web_page(SEED)), (C1, _web_page(C1, "<p>new</p>"))]))
    assert {c.metadata["url"] for c in chunks} == {C1}
    assert set(stale[0]["metadata.page_id"]) == {page_id(C1), page_id(SINGLE)}
    assert summary["pages_changed"] == 1 and summary["pages_deleted"] == 1 and SINGLE not in summary["pages"]


def test_an_unreadable_known_page_is_kept_and_an_unreadable_new_page_skipped():
    old = {C1: {"content_hash": "h", "title": "t"}}
    _chunks, _stale, summary = _run(_handler(old, [(SEED, _web_page(SEED)), (C1, None), (SINGLE, None)]))
    assert C1 in summary["pages"] and SINGLE not in summary["pages"] and summary["pages_deleted"] == 0


def test_point_ids_are_stable_per_page_chunk():
    a, _, _ = _run(_handler({}, [(SEED, _web_page(SEED, "<p>a</p>"))]))
    b, _, _ = _run(_handler({}, [(SEED, _web_page(SEED, "<p>b</p>"))]))
    assert a[0].id == b[0].id


# ── registration ─────────────────────────────────────────────────────────────

def _register(repo, upload_by="operator", **instance):
    return WebRegistration(repo, upload_by, {"urls": [SEED], **instance}).register()


def test_registration_stores_the_form_and_keeps_the_manifest():
    repo = MagicMock()
    repo.find_by_pipeline_id.return_value = DataSource(
        source_id="x", source_name="W", source_type="WEB", pipeline_id="p", upload_by="operator", created_at=None,
        type_data={"pages": {SEED: {"content_hash": "h"}}, "urls": ["old"]})
    source, issue = _register(repo, tags=["knowledge.tech"], metadata={"product": "P"}, maxPages=7)
    assert issue is None
    saved = repo.save.call_args.args[0]
    assert saved.source_type == "WEB" and saved.tags == ["knowledge.tech"]
    assert saved.type_data["pages"] == {SEED: {"content_hash": "h"}} and saved.type_data["urls"] == [SEED]
    assert saved.type_data["metadata"] == {"product": "P"} and saved.type_data["max_pages"] == 7
    assert source["pipeline_id"].startswith("web_")


@pytest.mark.parametrize("instance,issue", [
    ({"urls": []}, "MissingField"),
    ({"urls": ["ftp://x"]}, "InvalidUrl"),
    ({"crawl": "everything"}, "InvalidValue"),
])
def test_registration_refuses_a_bad_form(instance, issue):
    ok, problem = WebRegistration(MagicMock(), "u", {"urls": [SEED], **instance}).run_validator()
    assert not ok and problem["issue_type"] == issue


def test_same_seeds_give_the_same_source_id_in_any_order():
    a = WebRegistration(MagicMock(), "u", {"urls": [SEED, C1]})
    b = WebRegistration(MagicMock(), "u", {"urls": [C1, SEED]})
    assert a.source_data.source_id == b.source_data.source_id
