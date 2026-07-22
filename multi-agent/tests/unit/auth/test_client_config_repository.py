"""Unit tests for MongoServerConfigStore category listing (mocked collection)."""

from __future__ import annotations

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
