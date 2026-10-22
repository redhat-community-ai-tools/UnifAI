"""Session requirement, upload name validation, Slack signature and source update whitelist."""
import base64
import hashlib
import hmac
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from core.data_sources.service import EDITABLE_SOURCE_FIELDS
from infrastructure.http.slack_signature import verify_slack_signature
from infrastructure.storage.local_file_storage import LocalFileStorage

pytestmark = pytest.mark.unit


@pytest.fixture
def client():
    from infrastructure.http import docs, slack, vector, data_sources

    app = Flask(__name__)
    app.secret_key = "t"
    app.extensions["redis_kv_store"] = MagicMock()
    for bp, prefix in (
        (docs.docs_bp, "/api/docs/"),
        (slack.slack_bp, "/api/slack/"),
        (vector.vector_bp, "/api/vector/"),
        (data_sources.data_sources_bp, "/api/data_sources/"),
    ):
        app.register_blueprint(bp, url_prefix=prefix)
    return app.test_client()


PROTECTED = [
    ("post", "/api/docs/upload", {"files": []}),
    ("put", "/api/slack/fetch.available.slack.channels", None),
    ("get", "/api/slack/available.slack.channels.get?types=public_channel", None),
    ("get", "/api/slack/slack.channel.chunks?channel_name=c", None),
    ("get", "/api/slack/user.info.get", None),
    ("get", "/api/slack/stats", None),
    ("get", "/api/vector/chunks.counts", None),
    ("put", "/api/data_sources/data.source.update", {"source_id": "s", "updates": {}}),
]


@pytest.mark.parametrize("method,url,body", PROTECTED)
def test_anonymous_is_denied(client, method, url, body):
    resp = getattr(client, method)(url, json=body) if body is not None else getattr(client, method)(url)
    assert resp.status_code in (401, 403)


# ── Slack signature ──────────────────────────────────────────────────────────
def _sign(secret: str, body: bytes, ts: str) -> str:
    return "v0=" + hmac.new(secret.encode(), b"v0:" + ts.encode() + b":" + body, hashlib.sha256).hexdigest()


class TestSlackSignature:
    def test_valid_signature(self):
        ts = str(int(time.time()))
        assert verify_slack_signature("s3", b"{}", ts, _sign("s3", b"{}", ts))

    def test_wrong_secret_or_body_rejected(self):
        ts = str(int(time.time()))
        assert not verify_slack_signature("s3", b"{}", ts, _sign("other", b"{}", ts))
        assert not verify_slack_signature("s3", b"{x}", ts, _sign("s3", b"{}", ts))

    def test_stale_timestamp_rejected(self):
        ts = str(int(time.time()) - 3600)
        assert not verify_slack_signature("s3", b"{}", ts, _sign("s3", b"{}", ts))

    def test_missing_secret_fails_closed(self):
        ts = str(int(time.time()))
        assert not verify_slack_signature("", b"{}", ts, _sign("", b"{}", ts))

    def test_malformed_timestamp_rejected(self):
        assert not verify_slack_signature("s3", b"{}", "abc", "v0=x")

    def test_events_endpoint_requires_signature(self, client):
        from infrastructure.http import slack

        cfg = SimpleNamespace(slack_signing_secret="s3")
        with patch.object(slack.AppConfig, "get_instance", return_value=cfg), \
             patch.object(slack, "slack_event_dispatch_service") as svc:
            bad = client.post("/api/slack/events", json={"type": "event_callback"})
            assert bad.status_code == 401
            svc.assert_not_called()

            body = b'{"type": "url_verification", "challenge": "abc"}'
            ts = str(int(time.time()))
            svc.return_value.handle_webhook.return_value = SimpleNamespace(event_type="url_verification", message="abc")
            ok = client.post(
                "/api/slack/events", data=body, content_type="application/json",
                headers={"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": _sign("s3", body, ts)},
            )
            assert ok.status_code == 200 and ok.get_data(as_text=True) == "abc"


# ── Upload file names ────────────────────────────────────────────────────────
class TestUploadNames:
    @pytest.mark.parametrize("name", ["../x.pdf", "a/b.pdf", "..\\x.pdf", "/etc/passwd", "..", ".", "a\x00.pdf", "", "  "])
    def test_unsafe_names_rejected(self, tmp_path, name):
        storage = LocalFileStorage(str(tmp_path / "up"))
        with pytest.raises(ValueError):
            storage.save_files([{"name": name, "content": base64.b64encode(b"x").decode()}])
        assert list((tmp_path / "up").iterdir()) == []
        assert not (tmp_path / "x.pdf").exists()

    def test_plain_name_saved(self, tmp_path):
        storage = LocalFileStorage(str(tmp_path))
        paths = storage.save_files([{"name": "report v1.pdf", "content": base64.b64encode(b"x").decode()}])
        assert paths == [str(tmp_path / "report_v1.pdf")]

    def test_symlink_escape_rejected(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        up = tmp_path / "up"
        storage = LocalFileStorage(str(up))
        (up / "link.txt").symlink_to(outside / "target.txt")
        with pytest.raises(ValueError):
            storage.save("link.txt", b"x")
        assert not (outside / "target.txt").exists()


# ── Data source update whitelist ─────────────────────────────────────────────
class TestSourceUpdateWhitelist:
    @pytest.fixture
    def service(self):
        from core.data_sources.service import DataSourceService
        repo = MagicMock()
        svc = DataSourceService(repo, MagicMock(), MagicMock())
        return svc, repo

    def test_whitelist_excludes_ownership_and_access(self):
        assert not {"upload_by", "acl_groups", "visibility", "source_id", "pipeline_id"} & EDITABLE_SOURCE_FIELDS

    @pytest.mark.parametrize("field", ["upload_by", "acl_groups", "visibility", "access_scope"])
    def test_protected_field_rejected(self, service, field):
        svc, repo = service
        with pytest.raises(ValueError):
            svc.update("s", {"tags": ["a"], field: "x"}, upload_by="alice")
        repo.save.assert_not_called()

    def test_editable_fields_applied(self, service):
        svc, repo = service
        source = SimpleNamespace(tags=[], source_name="a", upload_by="alice")
        repo.find_by_id.return_value = source
        assert svc.update("s", {"tags": ["x"], "source_name": "b"}, upload_by="alice") is True
        assert source.tags == ["x"] and source.source_name == "b" and source.upload_by == "alice"
