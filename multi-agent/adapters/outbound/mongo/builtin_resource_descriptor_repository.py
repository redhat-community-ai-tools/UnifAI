import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pymongo

from mas.core.enums import ResourceOwnership, ResourceVisibility
from mas.core.identity import Identity
from mas.resources.builtin_models import BuiltinResourceDescriptor
from mas.resources.models import Resource
from mas.resources.repository.builtin_resource_descriptor_repository import (
    BuiltinResourceDescriptorRepository as BuiltinResourceDescriptorRepositoryPort,
)
from outbound.mongo.helpers import identity_q

logger = logging.getLogger(__name__)


class MongoBuiltinResourceDescriptorRepository(BuiltinResourceDescriptorRepositoryPort):
    """Mongo-backed built-in descriptor storage, plus ``$lookup``-joined
    reads against the base ``resources`` collection.

    Needs handles to *both* collections — the descriptor collection it
    owns, and the ``resources`` collection it joins against for
    ``find_all_builtins``/``find_visible_for_identity`` — since a
    ``Resource`` document alone carries no built-in-related fields to
    filter/sort on.
    """

    def __init__(
        self,
        mongodb_port: str = "27017",
        mongodb_ip: str = "localhost",
        db_name: str = "UnifAI",
        coll_name: str = "builtin_resource_descriptors",
        resources_coll_name: str = "resources",
    ) -> None:
        mongo_uri = f"mongodb://{mongodb_ip}:{mongodb_port}/"
        self._client = pymongo.MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        self.col = self._client[db_name][coll_name]
        self._resources_col = self._client[db_name][resources_coll_name]
        try:
            self.col.create_index("visibility", background=True)
        except pymongo.errors.PyMongoError:
            logger.warning(
                "Could not create indexes on '%s' — MongoDB may be unreachable",
                coll_name, exc_info=True,
            )

    # ---------- CRUD ----------
    def get(self, rid: str) -> Optional[BuiltinResourceDescriptor]:
        raw = self.col.find_one({"_id": rid})
        return BuiltinResourceDescriptor(**raw) if raw else None

    def save(self, descriptor: BuiltinResourceDescriptor) -> str:
        descriptor.updated = datetime.now(timezone.utc)
        doc = {"_id": descriptor.rid, **descriptor.model_dump(mode="json")}
        self.col.replace_one({"_id": descriptor.rid}, doc, upsert=True)
        return descriptor.rid

    def delete(self, rid: str) -> None:
        self.col.delete_one({"_id": rid})

    def find_all_rids(self) -> List[str]:
        return [doc["_id"] for doc in self.col.find({}, {"_id": 1})]

    # ---------- joined reads ----------
    def find_all_builtins(
        self,
        category: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> List[Resource]:
        """Every built-in resource (public and draft), unconditionally.

        Anchored on the (small, admin-curated) descriptor collection and
        ``$lookup``-joined into ``resources`` — cheaper than scanning the
        much larger ``resources`` collection for a category/type match
        first.
        """
        pipeline: List[Dict[str, Any]] = [
            {
                "$lookup": {
                    "from": self._resources_col.name,
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "resource",
                }
            },
            {"$unwind": "$resource"},
        ]
        if category:
            pipeline.append({"$match": {"resource.category": category}})
        if resource_type:
            pipeline.append({"$match": {"resource.type": resource_type}})
        pipeline.append({"$replaceRoot": {"newRoot": "$resource"}})

        return [Resource(**doc) for doc in self.col.aggregate(pipeline)]

    def find_visible_for_identity(
        self,
        *,
        identity: Optional[Identity],
        category: Optional[str],
        resource_type: Optional[str],
        ownership: Optional[ResourceOwnership],
        is_admin: bool,
        limit: int,
        offset: int,
        sort_by: str,
        sort_order: str,
    ) -> Tuple[List[Resource], int]:
        """Paginated resources visible to *identity*, joined with built-in
        descriptor metadata — see the port's docstring for the three
        ``ownership`` modes.

        Anchored on ``resources`` (unlike ``find_all_builtins``) since the
        default/custom modes must include the identity's own non-built-in
        resources, which have no descriptor to anchor on at all.
        """
        if limit is not None and limit < 0:
            raise ValueError(f"limit must be non-negative, got {limit}")

        base_match: Dict[str, Any] = {}
        if category:
            base_match["category"] = category
        if resource_type:
            base_match["type"] = resource_type

        identity_cond: Dict[str, Any] = identity_q(identity)

        # For CUSTOM mode, scope to the caller's own resources before the
        # $lookup so the join operates on a smaller working set.
        pre_lookup_match: Dict[str, Any] = dict(base_match)
        if ownership == ResourceOwnership.CUSTOM:
            pre_lookup_match.update(identity_cond)

        pipeline: List[Dict[str, Any]] = []
        if pre_lookup_match:
            pipeline.append({"$match": pre_lookup_match})
        pipeline.append({
            "$lookup": {
                "from": self.col.name,
                "localField": "_id",
                "foreignField": "_id",
                "as": "_descriptor",
            }
        })
        pipeline.append({"$addFields": {"_descriptor": {"$arrayElemAt": ["$_descriptor", 0]}}})

        if ownership == ResourceOwnership.BUILTIN:
            cond: Dict[str, Any] = {"_descriptor": {"$ne": None}}
            if not is_admin:
                cond["_descriptor.visibility"] = ResourceVisibility.PUBLIC.value
        elif ownership == ResourceOwnership.CUSTOM:
            cond = {"_descriptor": None}
        else:
            cond = {
                "$or": [
                    identity_cond,
                    {"_descriptor.visibility": ResourceVisibility.PUBLIC.value},
                ]
            }
        pipeline.append({"$match": cond})

        sort_direction = pymongo.DESCENDING if sort_order == "desc" else pymongo.ASCENDING
        pipeline.append({
            "$facet": {
                "metadata": [{"$count": "total"}],
                "data": [
                    {"$sort": {sort_by: sort_direction}},
                    {"$skip": offset},
                    *([ {"$limit": limit} ] if limit else []),
                    {"$project": {"_descriptor": 0}},
                ],
            }
        })

        result = list(self._resources_col.aggregate(pipeline))
        facet = result[0] if result else {"metadata": [], "data": []}
        total = facet["metadata"][0]["total"] if facet["metadata"] else 0
        docs = facet["data"]
        return [Resource(**doc) for doc in docs], total
