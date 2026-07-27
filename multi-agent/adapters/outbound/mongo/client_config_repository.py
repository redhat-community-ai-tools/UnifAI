"""
MongoServerConfigStore — stores auth server configs in a dedicated collection.

Collection: client_configs
Index: unique on server_identifier
"""

from __future__ import annotations

import logging
from typing import Optional

from pymongo import MongoClient, ASCENDING

from mas.core.auth.credentials.models import ClientConfig
from mas.core.auth.credentials.ports import ServerConfigStore

logger = logging.getLogger(__name__)


class MongoServerConfigStore(ServerConfigStore):

    def __init__(
        self,
        mongodb_ip: str = "127.0.0.1",
        mongodb_port: int = 27017,
        db_name: str = "unifai",
        coll_name: str = "server_configs",
    ):
        client = MongoClient(f"mongodb://{mongodb_ip}:{mongodb_port}/")
        db = client[db_name]
        self._coll = db[coll_name]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self._coll.create_index(
            [("server_identifier", ASCENDING)],
            unique=True,
            name="uq_server_identifier",
        )

    def find_by_server(self, user_id: str, server_identifier: str) -> Optional[ClientConfig]:
        if not server_identifier:
            return None
        normalized = server_identifier.rstrip("/")
        doc = self._coll.find_one({"server_identifier": normalized})
        return self._to_model(doc) if doc else None

    def save(self, user_id: str, config: ClientConfig) -> None:
        doc = config.model_dump()
        doc["server_identifier"] = config.server_identifier.rstrip("/")
        self._coll.update_one(
            {"server_identifier": doc["server_identifier"]},
            {"$set": doc},
            upsert=True,
        )

    @staticmethod
    def _to_model(doc: dict) -> ClientConfig:
        doc.pop("_id", None)
        return ClientConfig.model_validate(doc)
