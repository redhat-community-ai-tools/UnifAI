"""Unit tests for MongoServerConfigStore category listing (mocked collection)."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from outbound.mongo.client_config_repository import MongoServerConfigStore


def _store_with_coll(coll: MagicMock) -> MongoServerConfigStore:
    store = object.__new__(MongoServerConfigStore)
    store._coll = coll
    return store


class TestMongoServerConfigStoreListByCategory:
    def test_empty_category_returns_empty_without_query(self):
        coll = MagicMock()
        store = _store_with_coll(coll)

        assert store.list_by_category("") == []
        coll.find.assert_not_called()

    def test_queries_categories_and_maps_docs(self):
        coll = MagicMock()
        coll.find.return_value = [
            {
                "_id": "x",
                "client_id": "c1",
                "server_identifier": "https://auth.example/sso",
                "display_name": "RH SSO",
                "categories": ["a2a"],
            }
        ]
        store = _store_with_coll(coll)

        configs = store.list_by_category("a2a")

        coll.find.assert_called_once_with({"categories": "a2a"})
        assert len(configs) == 1
        assert configs[0].client_id == "c1"
        assert configs[0].server_identifier == "https://auth.example/sso"
        assert configs[0].display_name == "RH SSO"
        assert configs[0].categories == ["a2a"]

    def test_skips_invalid_docs_and_returns_valid_ones(self, monkeypatch):
        monkeypatch.delenv("ALLOW_INSECURE_OAUTH_ENDPOINTS", raising=False)
        coll = MagicMock()
        coll.find.return_value = [
            {
                "_id": "bad",
                "client_id": "bad-client",
                "server_identifier": "https://legacy.example/sso",
                "display_name": "Legacy private IP",
                "categories": ["a2a"],
                "token_endpoint": "https://10.0.0.5/token",
            },
            {
                "_id": "good",
                "client_id": "good-client",
                "server_identifier": "https://auth.example/sso",
                "display_name": "Good SSO",
                "categories": ["a2a"],
                "token_endpoint": "https://auth.example/token",
            },
        ]
        store = _store_with_coll(coll)

        configs = store.list_by_category("a2a")

        assert len(configs) == 1
        assert configs[0].client_id == "good-client"
        assert configs[0].server_identifier == "https://auth.example/sso"

    def test_invalid_doc_log_omits_secret_values(self, monkeypatch, caplog):
        monkeypatch.delenv("ALLOW_INSECURE_OAUTH_ENDPOINTS", raising=False)
        secret = "super-secret-client-value"
        coll = MagicMock()
        coll.find.return_value = [
            {
                "_id": "bad",
                "client_id": "bad-client",
                "client_secret": secret,
                "server_identifier": "https://legacy.example/sso",
                "categories": ["a2a"],
                "token_endpoint": "https://10.0.0.5/token",
            },
        ]
        store = _store_with_coll(coll)

        with caplog.at_level(logging.WARNING):
            assert store.list_by_category("a2a") == []

        joined = " ".join(caplog.messages)
        assert "https://legacy.example/sso" in joined
        assert secret not in joined


class TestMongoServerConfigStoreFindByServer:
    def test_returns_none_for_invalid_doc(self, monkeypatch):
        monkeypatch.delenv("ALLOW_INSECURE_OAUTH_ENDPOINTS", raising=False)
        coll = MagicMock()
        coll.find_one.return_value = {
            "_id": "bad",
            "client_id": "bad-client",
            "server_identifier": "https://legacy.example/sso",
            "token_endpoint": "https://169.254.169.254/latest/meta-data/",
        }
        store = _store_with_coll(coll)

        assert store.find_by_server("", "https://legacy.example/sso") is None
        coll.find_one.assert_called_once_with(
            {"server_identifier": "https://legacy.example/sso"}
        )
