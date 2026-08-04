import logging
from datetime import datetime, timezone
from typing import List, Optional

import pymongo

from mas.resources.builtin_models import BuiltinUserConfig
from mas.resources.repository.builtin_user_config_repository import (
    BuiltinUserConfigRepository as BuiltinUserConfigRepositoryPort,
)

logger = logging.getLogger(__name__)


class MongoBuiltinUserConfigRepository(BuiltinUserConfigRepositoryPort):
    def __init__(
        self,
        mongodb_port: str = "27017",
        mongodb_ip: str = "localhost",
        db_name: str = "UnifAI",
        coll_name: str = "builtin_user_configs",
    ) -> None:
        mongo_uri = f"mongodb://{mongodb_ip}:{mongodb_port}/"
        self._client = pymongo.MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        self.col = self._client[db_name][coll_name]
        # Bounded by the client timeouts above, so a Mongo outage at startup
        # fails fast rather than hanging. The index creation is retried on
        # every process start, so a transient failure here just means the
        # unique constraint isn't enforced until the next successful start —
        # not fatal enough to crash the whole app at boot.
        try:
            self.col.create_index(
                [("resource_id", 1), ("identity_key", 1)],
                unique=True,
                name="uq_resource_identity",
            )
            self.col.create_index("identity_key")
        except pymongo.errors.PyMongoError:
            logger.warning(
                "Could not create indexes on '%s' — MongoDB may be unreachable",
                coll_name, exc_info=True,
            )

    def save(self, config: BuiltinUserConfig) -> str:
        config.updated = datetime.now(timezone.utc)
        fields = config.model_dump(mode="json")
        fields.pop("config_id", None)
        doc = self.col.find_one_and_update(
            {"resource_id": config.resource_id, "identity_key": config.identity_key},
            {
                "$set": fields,
                "$setOnInsert": {"_id": config.config_id, "config_id": config.config_id},
            },
            upsert=True,
            return_document=pymongo.ReturnDocument.AFTER,
        )
        return doc["config_id"]

    def get(self, resource_id: str, identity_key: str) -> Optional[BuiltinUserConfig]:
        raw = self.col.find_one({
            "resource_id": resource_id,
            "identity_key": identity_key,
        })
        return BuiltinUserConfig(**raw) if raw else None

    def get_by_id(self, config_id: str) -> BuiltinUserConfig:
        raw = self.col.find_one({"_id": config_id})
        if not raw:
            raise KeyError(f"BuiltinUserConfig not found: {config_id}")
        return BuiltinUserConfig(**raw)

    def delete(self, resource_id: str, identity_key: str) -> None:
        self.col.delete_one({
            "resource_id": resource_id,
            "identity_key": identity_key,
        })

    def delete_all_for_resource(self, resource_id: str) -> int:
        result = self.col.delete_many({"resource_id": resource_id})
        return result.deleted_count

    def find_by_identity(self, identity_key: str) -> List[BuiltinUserConfig]:
        return [
            BuiltinUserConfig(**doc)
            for doc in self.col.find({"identity_key": identity_key})
        ]
