"""Confluence source: HTML normalisation, REST paging, incremental sync, idempotent registration."""
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import numpy as np
import pytest

from core.data_sources.domain.model import DataSource
from core.data_sources.types.confluence.pipeline_handler import (
    ConfluencePipelineHandler,
)
from core.data_sources.types.confluence.registration import ConfluenceRegistration
from core.pipeline.domain.port import PipelineContext
from core.pipeline.executor import PipelineExecutor
from infrastructure.sources.confluence.connector import (
    ConfluenceConnector,
    ConfluencePage,
)
from infrastructure.sources.confluence.html_text import html_to_text

pytestmark = pytest.mark.unit


def test_html_to_text_keeps_structure_and_drops_noise():
    html = ("<h2>Install</h2><p>Run <code>oc apply</code> now.</p><script>alert(1)</script>"
            "<ul><li>one</li><li>two</li></ul><table><tr><th>Key</th><th>Value</th></tr>"
            "<tr><td>port</td><td>8443</td></tr></table><pre>oc get pods</pre>"
            '<ac:structured-macro><ac:parameter ac:name="x">ignored</ac:parameter></ac:structured-macro>')
    text = html_to_text(html)
    assert "## Install" in text and "Run oc apply now." in text
    assert "- one" in text and "- two" in text
    assert "Key | Value" in text and "port | 8443" in text
    assert "```\noc get pods\n```" in text
    assert "alert" not in text and "ignored" not in text


# ── connector ────────────────────────────────────────────────────────────────

def _raw(pid, title, version=1, labels=()):
    return {"id": pid, "title": title, "version": {"number": version, "when": "2026-10-01T00:00:00Z"},
            "body": {"storage": {"value": f"<p>{title} body</p>"}}, "ancestors": [{"title": "Root"}],
            "metadata": {"labels": {"results": [{"name": lbl} for lbl in labels]}},
            "_links": {"webui": f"/spaces/SX/pages/{pid}", "base": "https://x.atlassian.net/wiki"}}


def _session(pages_by_cql):
    session = MagicMock()
    session.headers = {}

    def get(url, params=None, timeout=None):
        if params:
            key = params["cql"]
        else:
            key = url.split("cursor=")[-1]
        body = pages_by_cql[key]
        return SimpleNamespace(status_code=200, json=lambda b=body: b, text="")

    session.get.side_effect = get
    return session


def test_connector_resolves_the_root_follows_next_links_and_excludes_labels():
    session = _session({
        'space="SX" and type=page and title="Procédures"': {"results": [{"id": "10", "title": "Procédures"}]},
        "id=10": {"results": [_raw("10", "Procédures")]},
        "ancestor=10 and type=page": {"results": [_raw("11", "A")],
                                      "_links": {"next": "/rest/api/content/search?cursor=p2", "base": "https://x.atlassian.net/wiki"}},
        "p2": {"results": [_raw("12", "B", labels=["archived"]), _raw("13", "C")]},
    })
    conn = ConfluenceConnector("https://x.atlassian.net", "user", "token", session=session)
    pages = list(conn.iter_pages("SX", "Procédures", exclude_labels=["Archived"]))
    assert [p.page_id for p in pages] == ["10", "11", "13"]
    assert pages[1].url == "https://x.atlassian.net/wiki/spaces/SX/pages/11"
    second_page_url = session.get.call_args_list[-1].args[0]
    assert second_page_url == "https://x.atlassian.net/wiki/rest/api/content/search?cursor=p2"
    assert session.get.call_args_list[0].args[0] == "https://x.atlassian.net/wiki/rest/api/content/search"


# ── incremental pipeline ─────────────────────────────────────────────────────

def _page(pid, version):
    return ConfluencePage(page_id=pid, title=f"Page {pid}", version=version, last_modified="t",
                          url=f"https://c/{pid}", html=f"<p>content of {pid} v{version}</p>", ancestors=["Root"])


class FakeChunker:
    def chunk_content(self, docs):
        return [{"text": docs[0]["content"]}]


class FakeEmbedder:
    def generate_embeddings(self, chunks):
        return [{**c, "embedding": np.array([1.0, 0.0])} for c in chunks]


def _handler(manifest, live):
    sources = MagicMock()
    sources.get_by_id.return_value = SimpleNamespace(type_data={
        "base_url": "https://c", "space_key": "SX", "root_title": "", "exclude_labels": [], "pages": manifest})
    connector = MagicMock()
    connector.iter_pages.return_value = live
    return ConfluencePipelineHandler(lambda _url: connector, FakeChunker(), FakeEmbedder(), sources)


CTX = PipelineContext(pipeline_id="confluence_s1", source_type="CONFLUENCE", source_id="s1",
                      source_name="SX", owner_id="operator", metadata={})


def _run(handler):
    collected = handler.collect(CTX)
    chunks = handler.chunk_and_embed(CTX, handler.process(CTX, collected))
    return chunks, handler.stale_point_filters(CTX), handler.get_summary(CTX, collected)


def test_first_run_embeds_every_page():
    chunks, stale, summary = _run(_handler({}, [_page("1", 1), _page("2", 1)]))
    assert {c.metadata["page_id"] for c in chunks} == {"1", "2"}
    assert stale == [{"metadata.source_id": "s1", "metadata.page_id": ["1", "2"]}]
    assert summary["pages"] == {"1": {"version": 1, "title": "Page 1"}, "2": {"version": 1, "title": "Page 2"}}


def test_unchanged_space_embeds_nothing():
    manifest = {"1": {"version": 1}, "2": {"version": 1}}
    chunks, stale, summary = _run(_handler(manifest, [_page("1", 1), _page("2", 1)]))
    assert chunks == [] and stale == [] and summary["pages_unchanged"] == 2


def test_changed_and_deleted_pages_are_replaced_and_removed():
    manifest = {"1": {"version": 1}, "2": {"version": 1}, "3": {"version": 4}}
    chunks, stale, summary = _run(_handler(manifest, [_page("1", 1), _page("2", 2)]))
    assert {c.metadata["page_id"] for c in chunks} == {"2"}
    assert stale == [{"metadata.source_id": "s1", "metadata.page_id": ["2", "3"]}]
    assert summary["pages_changed"] == 1 and summary["pages_deleted"] == 1 and set(summary["pages"]) == {"1", "2"}


def test_point_ids_are_stable_per_page_chunk():
    a, _, _ = _run(_handler({}, [_page("1", 1)]))
    b, _, _ = _run(_handler({}, [_page("1", 2)]))
    assert a[0].id == b[0].id


def test_executor_deletes_stale_points_before_storing():
    repo = MagicMock()
    handler = MagicMock(source_type="CONFLUENCE")
    handler.chunk_and_embed.return_value = []
    handler.stale_point_filters.return_value = [{"metadata.page_id": ["2"]}]
    ex = PipelineExecutor(pipeline_service=MagicMock(), monitoring_service=MagicMock(),
                          data_source_service=MagicMock(), vector_repository=lambda _name: repo)
    ex.execute(handler, CTX)
    assert repo.method_calls[:2] == [call.delete_by_filter({"metadata.page_id": ["2"]}), call.store([])]


# ── registration ─────────────────────────────────────────────────────────────

def _register(repo, upload_by="operator", **instance):
    reg = ConfluenceRegistration(repo, upload_by, {"baseUrl": "https://c", "spaceKey": "SX", **instance})
    return reg.register()


def test_reregistration_keeps_the_sync_manifest():
    repo = MagicMock()
    repo.find_by_pipeline_id.return_value = DataSource(
        source_id="x", source_name="SX", source_type="CONFLUENCE", pipeline_id="p", upload_by="operator",
        created_at=None, type_data={"pages": {"1": {"version": 3}}, "base_url": "old"})
    source, issue = _register(repo, rootTitle="")
    assert issue is None
    saved = repo.save.call_args.args[0]
    assert saved.type_data["pages"] == {"1": {"version": 3}} and saved.type_data["base_url"] == "https://c"
    assert source["pipeline_id"].startswith("confluence_")


def test_reregistration_by_another_user_is_refused():
    repo = MagicMock()
    repo.find_by_pipeline_id.return_value = DataSource(
        source_id="x", source_name="SX", source_type="CONFLUENCE", pipeline_id="p", upload_by="operator", created_at=None)
    with pytest.raises(PermissionError):
        _register(repo, upload_by="mallory")


def test_same_scope_gives_the_same_source_id():
    r1 = ConfluenceRegistration(MagicMock(), "u", {"baseUrl": "https://c/", "spaceKey": "SX", "rootTitle": "R"})
    r2 = ConfluenceRegistration(MagicMock(), "u", {"baseUrl": "https://c", "spaceKey": "SX", "rootTitle": "R"})
    assert r1.source_data.source_id == r2.source_data.source_id


def test_deployment_credentials_go_only_to_listed_hosts():
    from infrastructure.sources.confluence.connector import credentials_allowed

    allowed = ["startxfr.atlassian.net"]
    assert credentials_allowed("https://startxfr.atlassian.net/wiki", allowed)
    assert credentials_allowed("https://STARTXFR.atlassian.net", allowed)
    assert not credentials_allowed("https://evil.example", allowed)
    assert not credentials_allowed("https://evil.atlassian.net", allowed)
    assert not credentials_allowed("https://startxfr.atlassian.net.evil.example", allowed)
    assert not credentials_allowed("https://startxfr.atlassian.net@evil.example/", allowed)
    assert not credentials_allowed("https://startxfr.atlassian.net", [])
    assert not credentials_allowed("", allowed)
