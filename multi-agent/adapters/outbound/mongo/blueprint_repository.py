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
        """Replace an existing draft.

        This is the *legacy* path (no OCC).  Kept for compatibility with
        callers that do not perform version snapshotting.  New code should
        call :meth:`update_with_version` instead.
        """
        # Fetch current document to run existence check.
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

    def update_with_version(
        self,
        *,
        blueprint_id: str,
        spec: BlueprintDraft,
        rid_refs: list[str],
        expected_version: int,
    ) -> Optional[BlueprintDocument]:
        """Replace an existing draft with optimistic concurrency control (OCC).

        The update is only applied when the stored ``version`` matches
        ``expected_version``.  On success the stored version is atomically
        incremented to ``expected_version + 1``.

        Args:
            blueprint_id: Target blueprint.
            spec: New draft spec to persist.
            rid_refs: Resolved external resource IDs.
            expected_version: The version the caller read before making
                changes.  Acts as an OCC guard.

        Returns:
            Updated :class:`BlueprintDocument` (new version), or ``None``
            when the OCC check fails (another writer already bumped the
            version).
        """
        new_version = expected_version + 1
        result = self._col.find_one_and_update(
            # OCC guard: only match if the version is exactly what we expect.
            {"blueprint_id": blueprint_id, "version": expected_version},
            {
                "$set": {
                    "spec_dict": spec.model_dump(mode="json"),
                    "rid_refs": rid_refs,
                    "version": new_version,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            return_document=pymongo.ReturnDocument.AFTER,
        )
        if result is None:
            return None  # Version mismatch — concurrent write detected.
        return BlueprintDocument(**result)
    
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
