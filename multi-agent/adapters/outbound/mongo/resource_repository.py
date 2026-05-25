from typing import List, Dict, Any
import pymongo
from mas.resources.models import Resource, ResourceQuery
from mas.resources.repository.base import ResourceRepository
from mas.core.identity import Identity
from mas.core.dto import GroupedCount
from outbound.mongo.helpers import identity_q


class MongoResourceRepository(ResourceRepository):
    def __init__(self, mongodb_port: str = "27017",
                 mongodb_ip: str = "localhost",
                 db_name="UnifAI",
                 coll_name="resources"):
        mongo_uri = f"mongodb://{mongodb_ip}:{mongodb_port}/"
        self._client = pymongo.MongoClient(mongo_uri)
        self.col = self._client[db_name][coll_name]
        self.col.create_index("nested_refs")
        self.col.create_index(
            [("identity.type", 1), ("identity.id", 1),
             ("category", 1), ("type", 1), ("name", 1)],
            name="uq_identity_cat_type_name",
            unique=True)
        self.col.create_index(
            [("identity.type", 1), ("identity.id", 1), ("created", -1)],
            background=True)

    # ---------- CRUD ----------
    def save(self, doc: Resource) -> str:
        """Insert a new resource document (create only)."""
        result = self.col.insert_one({"_id": doc.rid,
                                      **doc.model_dump(mode="json")})
        if not result.acknowledged:
            raise RuntimeError(f"Failed to insert document with rid: {doc.rid}")
        return doc.rid

    def update(self, doc: Resource) -> str:
        """Update an existing resource document."""
        result = self.col.replace_one(
            {"_id": doc.rid},
            doc.model_dump(mode="json")
        )
        if result.matched_count == 0:
            raise KeyError(f"No document found with rid: {doc.rid}")
        return doc.rid

    def get(self, rid: str) -> Resource:
        raw = self.col.find_one({"_id": rid})
        if not raw:
            raise KeyError(rid)
        return Resource(**raw)

    def delete(self, rid: str) -> None:
        self.col.delete_one({"_id": rid})

    def delete_by_identity(self, identity: Identity) -> int:
        """Delete all resources owned by the given identity. Returns count."""
        result = self.col.delete_many(identity_q(identity))
        return result.deleted_count

    def find_by_name(self, identity: Identity, category: str,
                     type: str, name: str):
        q = {**identity_q(identity),
             "category": category, "type": type, "name": name}
        raw = self.col.find_one(q)
        return Resource(**raw) if raw else None

    # ---------- queries ----------
    def find_resources(self, query: ResourceQuery) -> List[Resource]:
        """Find resources based on query criteria with pagination."""
        filter_dict = identity_q(query.identity)

        if query.category:
            filter_dict["category"] = query.category.value
        if query.type:
            filter_dict["type"] = query.type

        # Build cursor with filtering
        cursor = self.col.find(filter_dict)

        # Apply sorting
        sort_direction = pymongo.DESCENDING if query.sort_order == "desc" else pymongo.ASCENDING
        cursor = cursor.sort(query.sort_by, sort_direction)

        # Apply pagination
        if query.offset:
            cursor = cursor.skip(query.offset)
        if query.limit:
            cursor = cursor.limit(query.limit)

        return [Resource(**doc) for doc in cursor]

    def count_resources(self, query: ResourceQuery) -> int:
        """Count resources matching query criteria."""
        filter_dict = identity_q(query.identity)

        if query.category:
            filter_dict["category"] = query.category.value
        if query.type:
            filter_dict["type"] = query.type

        return self.col.count_documents(filter_dict)

    def count(self, identity: Identity, filter: dict | None = None) -> int:
        # Identity keys must not be overridden by caller-supplied filter.
        merged = {**(filter or {}), **identity_q(identity)}
        return self.col.count_documents(merged)

    def meta(self, rid: str) -> tuple[str, str]:
        doc = self.col.find_one({"_id": rid}, {"category": 1, "type": 1})
        if not doc:
            raise KeyError(rid)
        return doc["category"], doc["type"]

    def count_nested(self, rid: str) -> int:
        return self.col.count_documents({"cfg_dict": {"$regex": rid}})

    def list_nested_usage(self, rid: str) -> List[str]:
        cur = self.col.find({"nested_refs": rid}, {"_id": 1})
        return [doc["_id"] for doc in cur]

    def exists(self, rid: str) -> bool:
        return self.col.count_documents({"_id": rid}, limit=1) == 1

    def count_by_config_field(
        self,
        identity: Identity,
        field: str,
        value: str,
        exclude_rid: str = "",
    ) -> int:
        filter_dict: Dict[str, Any] = {
            **identity_q(identity),
            f"cfg_dict.{field}": value,
        }
        if exclude_rid:
            filter_dict["_id"] = {"$ne": exclude_rid}
        return self.col.count_documents(filter_dict)

    def group_count(
        self,
        identity: Identity,
        group_by: List[str],
        filter: Dict[str, Any] | None = None,
    ) -> List[GroupedCount]:
        """
        Group documents by specified fields and return counts.
        Uses MongoDB aggregation for efficient server-side grouping.
        
        Transforms MongoDB's {"_id": {...}, "count": N} format to 
        database-agnostic GroupedCount DTOs.
        """
        match = {**(filter or {}), **identity_q(identity)}
        group_id = {field: f"${field}" for field in group_by}
        
        pipeline = [
            {"$match": match},
            {"$group": {"_id": group_id, "count": {"$sum": 1}}}
        ]

        # Transform MongoDB format → clean DTO
        return [
            GroupedCount(fields=doc["_id"], count=doc["count"])
            for doc in self.col.aggregate(pipeline)
        ]
