import pymongo
from uuid import uuid4
from datetime import datetime, timezone
from typing import List, Dict, Any
from mas.blueprints.models.blueprint import BlueprintDraft, BlueprintDocument, BlueprintSummary
from mas.blueprints.repository.repository import BlueprintRepository
from mas.core.enums import ResourceCategory
from global_utils.utils.util import get_mongo_url


class MongoBlueprintRepository(BlueprintRepository):
    def __init__(self,
                 db_name="UnifAI",
                 coll_name="blueprints"):
        mongo_uri = get_mongo_url()
        client = pymongo.MongoClient(mongo_uri)
        self._col = client[db_name][coll_name]
        self._col.create_index([("blueprint_id", pymongo.ASCENDING)], unique=True)
        self._col.create_index("rid_refs")

    def save(self, user_id, spec: BlueprintDraft, rid_refs: list[str], metadata: Dict[str, Any] = {}) -> str:
        new_id = str(uuid4())
        doc = {
            "blueprint_id": new_id,
            "user_id": user_id,
            "created_at": getattr(spec, "created_at", datetime.now(timezone.utc)),
            "updated_at": datetime.now(timezone.utc),
            "spec_dict": spec.model_dump(mode="json"),
            "rid_refs": rid_refs,
            "metadata": metadata
        }
        self._col.insert_one(doc)
        return new_id

    def update(self, *, blueprint_id: str, spec: BlueprintDraft,
               rid_refs: list[str]) -> bool:
        # Fetch current document to obtain user_id and run existence checks
        existing = self._col.find_one({"blueprint_id": blueprint_id})
        if existing is None:
            raise KeyError(f"No blueprint with id={blueprint_id}")

        res = self._col.update_one(
            {"blueprint_id": blueprint_id},
            {"$set": {
                "spec_dict": spec.model_dump(mode="json"),
                "rid_refs": rid_refs,
                "updated_at": datetime.now(timezone.utc),
            }}
        )

        return res.modified_count == 1

    def set_metadata(self, *, blueprint_id: str, metadata: Dict[str, Any]) -> bool:
        """Set the metadata dictionary for a blueprint document."""
        if not isinstance(metadata, dict):
            raise ValueError(f"metadata must be a dictionary, got: {type(metadata)}")
        res = self._col.update_one(
            {"blueprint_id": blueprint_id},
            {"$set": {"metadata": metadata, "updated_at": datetime.now(timezone.utc)}}
        )
        return res.modified_count == 1

    def load(self, blueprint_id: str) -> BlueprintDocument:
        doc = self._col.find_one({"blueprint_id": blueprint_id})
        if not doc:
            raise KeyError(f"No blueprint with id={blueprint_id}")
        return BlueprintDocument(**doc)

    def delete(self, blueprint_id: str) -> bool:
        res = self._col.delete_one({"blueprint_id": blueprint_id})
        return res.deleted_count == 1

    def load_many(self, blueprint_ids: List[str]) -> List[BlueprintDocument]:
        """Load multiple blueprint documents by their IDs in a single $in query."""
        if not blueprint_ids:
            return []
        return [
            BlueprintDocument(**doc)
            for doc in self._col.find({"blueprint_id": {"$in": blueprint_ids}})
        ]

    def exists(self, blueprint_id: str) -> bool:
        return self._col.count_documents({"blueprint_id": blueprint_id}, limit=1) == 1

    # --------- listing & counting with optional user filter -------
    def _user_q(self, user_id: str | None) -> Dict[str, Any]:
        return {} if user_id is None else {"user_id": user_id}

    def list_ids(
            self, *, user_id: str | None = None, skip=0, limit=100, sort_desc=True
    ) -> List[str]:
        cur = (
            self._col.find(self._user_q(user_id), {"blueprint_id": 1})
            .sort("updated_at", pymongo.DESCENDING if sort_desc else pymongo.ASCENDING)
            .skip(skip)
            .limit(limit)
        )
        return [d["blueprint_id"] for d in cur]

    def list_docs(
            self,
            *,
            user_id: str | None = None,
            skip: int = 0,
            limit: int = 100,
            sort_desc: bool = True,
    ) -> List[BlueprintDocument]:
        """Return BlueprintDocument objects for bulk operations."""
        cursor = (
            self._col.find(self._user_q(user_id))
            .sort("updated_at", pymongo.DESCENDING if sort_desc else pymongo.ASCENDING)
            .skip(skip)
            .limit(limit)
        )
        return [BlueprintDocument(**raw) for raw in cursor]

    def list_summaries(
            self,
            *,
            user_id: str | None = None,
            skip: int = 0,
            limit: int = 100,
            sort_desc: bool = True,
    ) -> List[BlueprintSummary]:
        projection = {
            "_id": 0,
            "blueprint_id": 1,
            "user_id": 1,
            "created_at": 1,
            "updated_at": 1,
            "metadata": 1,
            "spec_dict.name": 1,
            "spec_dict.description": 1,
        }
        cursor = (
            self._col.find(self._user_q(user_id), projection)
            .sort("updated_at", pymongo.DESCENDING if sort_desc else pymongo.ASCENDING)
            .skip(skip)
            .limit(limit)
        )
        summaries = []
        for doc in cursor:
            spec = doc.get("spec_dict", {})
            summaries.append(BlueprintSummary(
                blueprint_id=doc["blueprint_id"],
                user_id=doc["user_id"],
                name=spec.get("name", "Untitled blueprint"),
                description=spec.get("description", ""),
                created_at=doc["created_at"],
                updated_at=doc["updated_at"],
                metadata=doc.get("metadata", {}),
            ))
        return summaries

    def list_direct_usage(self, rid: str) -> List[str]:
        cur = self._col.find({"rid_refs": rid}, {"blueprint_id": 1})
        return [doc["blueprint_id"] for doc in cur]

    def count_usage(self, rid: str) -> int:
        fields = [
                     f"spec_dict.{cat}.rid"  # direct catalogue entry
                     for cat in ResourceCategory.list_values()
                 ] + [
                     f"spec_dict.{cat}.config.rid"  # nested inside another resource
                     for cat in ResourceCategory.list_values()
                 ]
        ors = [{fld: rid} for fld in fields]
        return self._col.count_documents({"$or": ors})

    def count(self, user_id: str | None = None) -> int:
        return self._col.count_documents(self._user_q(user_id))
