"""
MongoDB implementation of ScheduledPromptRepository.

Manages the `scheduled_prompts` collection with TTL cleanup for
completed prompts and identity-scoped queries.
"""
import pymongo
from datetime import datetime, timezone
from typing import List

from mas.core.identity import Identity
from mas.prompts.models import ScheduledPrompt
from mas.prompts.repository import ScheduledPromptRepository
from outbound.mongo.helpers import identity_q
from global_utils.utils.util import get_mongo_url


class MongoScheduledPromptRepository(ScheduledPromptRepository):

    def __init__(self, db_name: str = "UnifAI", coll_name: str = "scheduled_prompts"):
        mongo_uri = get_mongo_url()
        client = pymongo.MongoClient(mongo_uri)
        self._col = client[db_name][coll_name]

        self._col.create_index([("id", pymongo.ASCENDING)], unique=True)
        self._col.create_index(
            [
                ("identity.type", pymongo.ASCENDING),
                ("identity.id", pymongo.ASCENDING),
                ("updated_at", pymongo.DESCENDING),
            ],
            background=True,
        )
        self._col.create_index("blueprint_id", background=True)
        self._col.create_index("schedule_status", background=True)
        try:
            self._col.create_index(
                "completed_at",
                expireAfterSeconds=604800,  # 7-day TTL
                partialFilterExpression={"completed_at": {"$type": "date"}},
                background=True,
            )
        except pymongo.errors.OperationFailure:
            self._col.drop_index("completed_at_1")
            self._col.create_index(
                "completed_at",
                expireAfterSeconds=604800,  # 7-day TTL
                partialFilterExpression={"completed_at": {"$type": "date"}},
                background=True,
            )

    def save(self, prompt: ScheduledPrompt) -> str:
        now = datetime.now(timezone.utc)
        doc = prompt.model_dump(mode="json")
        doc["created_at"] = now
        doc["updated_at"] = now
        self._col.insert_one(doc)
        return prompt.id

    def load(self, prompt_id: str) -> ScheduledPrompt:
        doc = self._col.find_one({"id": prompt_id})
        if not doc:
            raise KeyError(f"No scheduled prompt with id={prompt_id}")
        return self._deserialize(doc)

    def update(self, prompt: ScheduledPrompt) -> bool:
        now = datetime.now(timezone.utc)
        doc = prompt.model_dump(mode="json")
        doc["updated_at"] = now
        doc.pop("created_at", None)
        res = self._col.update_one(
            {"id": prompt.id},
            {"$set": doc},
        )
        return res.modified_count == 1

    def delete(self, prompt_id: str) -> bool:
        res = self._col.delete_one({"id": prompt_id})
        return res.deleted_count == 1

    def list_by_identity(
        self, identity: Identity, *, skip: int = 0, limit: int = 100,
    ) -> List[ScheduledPrompt]:
        query = identity_q(identity)
        cursor = (
            self._col.find(query)
            .sort("updated_at", pymongo.DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return [self._deserialize(doc) for doc in cursor]

    def find_by_blueprint(self, blueprint_id: str) -> List[ScheduledPrompt]:
        cursor = self._col.find({
            "blueprint_id": blueprint_id,
        }).sort("updated_at", pymongo.DESCENDING)
        return [self._deserialize(doc) for doc in cursor]

    def count_active_by_blueprint(self, blueprint_id: str) -> int:
        return self._col.count_documents({
            "blueprint_id": blueprint_id,
            "schedule_status": {"$in": ["active", "paused"]},
        })

    def record_run(self, prompt_id: str, session_id: str, status: str, started_at: datetime) -> None:
        entry = {
            "session_id": session_id,
            "status": status,
            "started_at": started_at,
        }
        self._col.update_one(
            {"id": prompt_id},
            {
                "$inc": {"run_stats.total_runs": 1},
                "$set": {"run_stats.last_run_at": started_at},
                "$push": {
                    "run_stats.recent_statuses": {
                        "$each": [entry],
                        "$slice": -8,
                    }
                },
            },
        )

    @staticmethod
    def _deserialize(doc: dict) -> ScheduledPrompt:
        doc.pop("_id", None)
        doc.pop("created_at", None)
        doc.pop("updated_at", None)
        return ScheduledPrompt(**doc)
