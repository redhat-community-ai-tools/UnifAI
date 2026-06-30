import pymongo
from uuid import uuid4
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from mas.blueprints.models.blueprint import BlueprintDraft, BlueprintDocument, BlueprintSummary
from mas.blueprints.repository.repository import BlueprintRepository
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from outbound.mongo.helpers import identity_q
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
        self._col.create_index(
            [("identity.type", pymongo.ASCENDING),
             ("identity.id", pymongo.ASCENDING),
             ("updated_at", pymongo.DESCENDING)],
            background=True,
        )

    def save(self, identity: Identity, spec: BlueprintDraft,
             rid_refs: list[str], metadata: Dict[str, Any] = {}) -> str:
        new_id = str(uuid4())
        doc = {
            "blueprint_id": new_id,
            "identity": identity.model_dump(mode="json"),
            "created_at": getattr(spec, "created_at", datetime.now(timezone.utc)),
            "updated_at": datetime.now(timezone.utc),
            "spec_dict": spec.model_dump(mode="json"),
            "rid_refs": rid_refs,
            "metadata": metadata,
        }
        self._col.insert_one(doc)
        return new_id

    def update(self, *, blueprint_id: str, spec: BlueprintDraft,
               rid_refs: list[str]) -> bool:
        # Fetch current document to obtain user_id and run existence checks
        existing = self._col.find_one({"blueprint_id": blueprint_id})
        if existing is None:
            raise KeyError(f"No blueprint with id={blueprint_id}")

        new_spec = spec.model_dump(mode="json")
        for key, value in (existing.get("spec_dict") or {}).items():
            if key not in new_spec:
                new_spec[key] = value

        res = self._col.update_one(
            {"blueprint_id": blueprint_id},
            {"$set": {
                "spec_dict": new_spec,
                "rid_refs": rid_refs,
                "updated_at": datetime.now(timezone.utc),
            }}
        )

        return res.modified_count == 1
    
    def set_metadata(self, *, blueprint_id: str, metadata: Dict[str, Any]) -> bool:
        """Set individual metadata keys using dot-notation (key-level merge)."""
        if not isinstance(metadata, dict):
            raise ValueError(f"metadata must be a dictionary, got: {type(metadata)}")
        update_fields = {f"metadata.{k}": v for k, v in metadata.items()}
        update_fields["updated_at"] = datetime.now(timezone.utc)
        res = self._col.update_one(
            {"blueprint_id": blueprint_id},
            {"$set": update_fields},
        )
        return res.modified_count == 1

    def set_prompt_shortcuts(self, *, blueprint_id: str, prompts: Optional[List[dict]]) -> bool:
        now = datetime.now(timezone.utc)
        if prompts:
            op = {"$set": {"spec_dict.prompt_shortcuts": prompts, "updated_at": now}}
        else:
            op = {"$unset": {"spec_dict.prompt_shortcuts": ""}, "$set": {"updated_at": now}}
        res = self._col.update_one({"blueprint_id": blueprint_id}, op)
        return res.matched_count >= 1

    def get_prompt_shortcuts(self, *, blueprint_id: str) -> Optional[List[dict]]:
        doc = self._col.find_one({"blueprint_id": blueprint_id}, {"spec_dict.prompt_shortcuts": 1})
        if not doc:
            raise KeyError(f"No blueprint with id={blueprint_id}")
        return (doc.get("spec_dict") or {}).get("prompt_shortcuts")

    def load(self, blueprint_id: str) -> BlueprintDocument:
        doc = self._col.find_one({"blueprint_id": blueprint_id})
        if not doc:
            raise KeyError(f"No blueprint with id={blueprint_id}")
        return BlueprintDocument(**doc)

    def delete(self, blueprint_id: str) -> bool:
        res = self._col.delete_one({"blueprint_id": blueprint_id})
        return res.deleted_count == 1

    def delete_by_identity(self, identity: Identity) -> int:
        """Delete all blueprints owned by the given identity. Returns count."""
        result = self._col.delete_many(identity_q(identity))
        return result.deleted_count

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

    # --------- listing & counting with identity filter -------

    def list_ids(
            self, *, identity: Optional[Identity] = None,
            skip=0, limit=100, sort_desc=True
    ) -> List[str]:
        cur = (
            self._col.find(identity_q(identity), {"blueprint_id": 1})
            .sort("updated_at", pymongo.DESCENDING if sort_desc else pymongo.ASCENDING)
            .skip(skip)
            .limit(limit)
        )
        return [d["blueprint_id"] for d in cur]

    def list_docs(
            self, *,
            identity: Optional[Identity] = None,
            skip: int = 0, limit: int = 100, sort_desc: bool = True,
    ) -> List[BlueprintDocument]:
        """Return BlueprintDocument objects for bulk operations."""
        cursor = (
            self._col.find(identity_q(identity))
            .sort("updated_at", pymongo.DESCENDING if sort_desc else pymongo.ASCENDING)
            .skip(skip)
            .limit(limit)
        )
        return [BlueprintDocument(**raw) for raw in cursor]

    def list_summaries(
            self, *,
            identity: Optional[Identity] = None,
            skip: int = 0, limit: int = 100, sort_desc: bool = True,
    ) -> List[BlueprintSummary]:
        projection = {
            "_id": 0,
            "blueprint_id": 1,
            "identity": 1,
            "created_at": 1,
            "updated_at": 1,
            "metadata": 1,
            "spec_dict.name": 1,
            "spec_dict.description": 1,
        }
        cursor = (
            self._col.find(identity_q(identity), projection)
            .sort("updated_at", pymongo.DESCENDING if sort_desc else pymongo.ASCENDING)
            .skip(skip)
            .limit(limit)
        )
        summaries = []
        for doc in cursor:
            spec = doc.get("spec_dict", {})
            summaries.append(BlueprintSummary(
                blueprint_id=doc["blueprint_id"],
                identity=Identity(**doc["identity"]),
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
                     f"spec_dict.{cat}.rid"
                     for cat in ResourceCategory.list_values()
                 ] + [
                     f"spec_dict.{cat}.config.rid"
                     for cat in ResourceCategory.list_values()
                 ]
        ors = [{fld: rid} for fld in fields]
        return self._col.count_documents({"$or": ors})

    def count(self, identity: Optional[Identity] = None) -> int:
        return self._col.count_documents(identity_q(identity))
