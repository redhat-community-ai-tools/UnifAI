"""
MongoDB implementation of WorkflowScheduleRepository.

Manages the `workflow_schedules` collection with TTL cleanup for
completed schedules and identity-scoped queries.
"""
from datetime import datetime, timezone
from typing import List

import pymongo

from mas.core.identity import Identity
from mas.scheduling.models import RunOutcome, WorkflowSchedule, ScheduleStatus
from mas.scheduling.repository import WorkflowScheduleRepository
from outbound.mongo.helpers import identity_q
from global_utils.utils.util import get_mongo_url


class MongoWorkflowScheduleRepository(WorkflowScheduleRepository):

    def __init__(self, db_name: str = "UnifAI", coll_name: str = "workflow_schedules"):
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

    def save(self, schedule: WorkflowSchedule) -> str:
        now = datetime.now(timezone.utc)
        doc = schedule.model_dump(mode="json")
        doc["created_at"] = now
        doc["updated_at"] = now
        self._col.insert_one(doc)
        return schedule.id

    def load(self, schedule_id: str) -> WorkflowSchedule:
        doc = self._col.find_one({"id": schedule_id})
        if not doc:
            raise KeyError(f"No workflow schedule with id={schedule_id}")
        return self._deserialize(doc)

    def update(self, schedule: WorkflowSchedule) -> bool:
        now = datetime.now(timezone.utc)
        doc = schedule.model_dump(mode="json")
        doc["updated_at"] = now
        doc.pop("created_at", None)
        if schedule.completed_at is not None:
            doc["completed_at"] = schedule.completed_at
        res = self._col.update_one(
            {"id": schedule.id},
            {"$set": doc},
        )
        return res.modified_count == 1

    def delete(self, schedule_id: str) -> bool:
        res = self._col.delete_one({"id": schedule_id})
        return res.deleted_count == 1

    def list_by_identity(
        self, identity: Identity, *, skip: int = 0, limit: int = 100,
    ) -> List[WorkflowSchedule]:
        query = identity_q(identity)
        cursor = (
            self._col.find(query)
            .sort("updated_at", pymongo.DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return [self._deserialize(doc) for doc in cursor]

    def find_by_blueprint(self, blueprint_id: str) -> List[WorkflowSchedule]:
        cursor = self._col.find({
            "blueprint_id": blueprint_id,
        }).sort("updated_at", pymongo.DESCENDING)
        return [self._deserialize(doc) for doc in cursor]

    def count_active_by_blueprint(self, blueprint_id: str) -> int:
        return self._col.count_documents({
            "blueprint_id": blueprint_id,
            "schedule_status": {"$in": [ScheduleStatus.ACTIVE, ScheduleStatus.PAUSED]},
        })

    def record_run(self, schedule_id: str, session_id: str, status: RunOutcome, started_at: datetime) -> None:
        entry = {
            "session_id": session_id,
            "status": status,
            "started_at": started_at,
        }
        result = self._col.update_one(
            {
                "id": schedule_id,
                "run_stats.recent_statuses.session_id": {"$ne": session_id},
            },
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
        if result.matched_count == 0:
            self._col.update_one(
                {
                    "id": schedule_id,
                    "run_stats.recent_statuses.session_id": session_id,
                },
                {
                    "$max": {"run_stats.last_run_at": started_at},
                    "$set": {"run_stats.recent_statuses.$.status": status},
                },
            )

    @staticmethod
    def _deserialize(doc: dict) -> WorkflowSchedule:
        doc.pop("_id", None)
        doc.pop("created_at", None)
        doc.pop("updated_at", None)
        return WorkflowSchedule(**doc)
