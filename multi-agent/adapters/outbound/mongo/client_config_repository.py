"""
MongoServerConfigStore — stores auth server configs in a dedicated collection.

Collection: server_configs
Index: unique on server_identifier, multikey on categories
"""

from __future__ import annotations

import logging
from typing import List, Optional

from pymongo import MongoClient, ASCENDING
from pydantic import ValidationError

from mas.core.auth.credentials.models import ClientConfig
from mas.core.auth.credentials.ports import ServerConfigStore

logger = logging.getLogger(__name__)


def _validation_error_summary(exc: ValidationError) -> list[dict]:
    """Return ValidationError details safe for logs (no rejected input values)."""
    return [
        {"loc": err.get("loc"), "type": err.get("type"), "msg": err.get("msg")}
        for err in exc.errors()
    ]


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
        self._coll.create_index(
            [("categories", ASCENDING)],
            name="idx_categories",
            sparse=True,
        )

    def find_by_server(self, user_id: str, server_identifier: str) -> Optional[ClientConfig]:
        if not server_identifier:
            return None
        normalized = server_identifier.rstrip("/")
        doc = self._coll.find_one({"server_identifier": normalized})
        return self._to_model(doc) if doc else None

    def save(self, user_id: str, config: ClientConfig) -> None:
        # exclude_none keeps omitted secrets from wiping existing values on update
        doc = config.model_dump(exclude_none=True)
        doc["server_identifier"] = config.server_identifier.rstrip("/")
        self._coll.update_one(
            {"server_identifier": doc["server_identifier"]},
            {"$set": doc},
            upsert=True,
        )

    def list_by_category(self, category: str) -> List[ClientConfig]:
        if not category:
            return []
        docs = self._coll.find({"categories": category})
        configs: List[ClientConfig] = []
        for doc in docs:
            cfg = self._to_model(doc)
            if cfg is not None:
                configs.append(cfg)
        return configs

    @staticmethod
    def _to_model(doc: dict) -> Optional[ClientConfig]:
        """Map a Mongo doc to ClientConfig; skip invalid docs (legacy / env mismatch)."""
        doc.pop("_id", None)
        try:
            return ClientConfig.model_validate(doc)
        except ValidationError as e:
            logger.warning(
                "Skipping invalid server_config server_identifier=%r: %s",
                doc.get("server_identifier"),
                _validation_error_summary(e),
            )
            return None
