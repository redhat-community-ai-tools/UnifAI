"""
MongoDB adapter for the Blueprint repository port.

Implements ``BlueprintRepository`` using PyMongo.  Pass an explicit
``col`` (``pymongo.collection.Collection``) to the constructor so that
unit tests can inject a ``mongomock`` collection without standing up a
real database.

GENIE-1336
----------
* ``save()`` initialises ``version: 1`` on every new document.
* ``update_with_version()`` uses ``find_one_and_update`` with an OCC
  filter on ``{blueprint_id, version}`` and ``$inc: {version: 1}``.
* ``_doc_to_model()`` back-fills ``version = 1`` for legacy documents
  that pre-date the GENIE-1336 migration.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from lib.mas.blueprints.models.blueprint import (
    BlueprintDocument,
    BlueprintSummary,
    Identity,
)
from lib.mas.blueprints.repository.repository import BlueprintRepository
from pymongo import DESCENDING, ReturnDocument
from pymongo.collection import Collection


class MongoBlueprintRepository(BlueprintRepository):
    """
    Concrete MongoDB adapter for ``BlueprintRepository``.

    Parameters
    ----------
    col:
        PyMongo (or mongomock) collection for ``blueprints``.
        When ``None``, the class raises ``RuntimeError`` on first use —
        pass a real collection at boot time via the DI container.
    """

    def __init__(self, col: Optional[Collection] = None) -> None:
        if col is None:
            raise RuntimeError(
                "MongoBlueprintRepository requires a non-None 'col' argument."
            )
        self._col: Collection = col

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def save(
        self,
        identity: Identity,
        spec: dict,
        rid_refs: List[str],
        metadata: Optional[dict] = None,
    ) -> str:
        """Insert a new blueprint document.  Always initialises ``version = 1``."""
        blueprint_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        doc: Dict[str, Any] = {
            "blueprint_id": blueprint_id,
            "identity": identity.model_dump(),
            "created_at": now,
            "updated_at": now,
            "spec_dict": spec,
            "rid_refs": rid_refs,
            "metadata": metadata or {},
            "version": 1,  # GENIE-1336
        }
        self._col.insert_one(doc)
        return blueprint_id

    def update(self, blueprint_id: str, spec: dict, rid_refs: List[str]) -> bool:
        """
        Unconditional spec update — no OCC guard, no version increment.

        Provided for backwards-compatibility with callers that have not
        yet migrated to ``update_with_version``.
        """
        now = datetime.now(timezone.utc)
        result = self._col.update_one(
            {"blueprint_id": blueprint_id},
            {
                "$set": {
                    "spec_dict": spec,
                    "rid_refs": rid_refs,
                    "updated_at": now,
                }
            },
        )
        return result.matched_count > 0

    def update_with_version(
        self,
        blueprint_id: str,
        spec: dict,
        rid_refs: List[str],
        expected_version: int,
    ) -> Optional[int]:
        """
        Atomic OCC-guarded spec update.

        The filter includes ``version: expected_version`` so the update
        is rejected if any concurrent writer has already bumped the version.

        **Pre-migration documents (no ``version`` field)**

        When ``expected_version == 1`` we perform *two* sequential attempts:

        1. Standard path — filter ``{"version": 1}``, use ``$inc: {version: 1}``
           → writes ``version: 2`` on documents that already have the field.
        2. Pre-migration fallback — filter ``{"version": {"$exists": False}}``,
           use ``$set: {version: 2}`` (NOT ``$inc``) → writes ``version: 2``
           on documents that were inserted before GENIE-1336.

        The reason we cannot use ``$inc`` for the pre-migration case is that
        MongoDB treats a missing field as 0 for increment purposes, so
        ``$inc: {version: 1}`` on a document without the field produces
        ``version: 1`` instead of the expected ``version: 2``.

        Returns the new version number on success, or ``None`` if the
        document was not found / the OCC guard failed.
        """
        now = datetime.now(timezone.utc)

        common_set: Dict[str, Any] = {
            "spec_dict": spec,
            "rid_refs": rid_refs,
            "updated_at": now,
        }

        if expected_version == 1:
            # --- Attempt 1: document already has version=1 (post-migration) ---
            updated_doc = self._col.find_one_and_update(
                filter={"blueprint_id": blueprint_id, "version": 1},
                update={
                    "$set": common_set,
                    "$inc": {"version": 1},
                },
                return_document=ReturnDocument.AFTER,
                projection={"version": 1},
            )

            if updated_doc is None:
                # --- Attempt 2: pre-migration document with NO version field ---
                # Must use $set instead of $inc: MongoDB treats a missing field
                # as 0, so $inc would produce version=1 not version=2.
                updated_doc = self._col.find_one_and_update(
                    filter={
                        "blueprint_id": blueprint_id,
                        "version": {"$exists": False},
                    },
                    update={
                        "$set": {**common_set, "version": 2},
                    },
                    return_document=ReturnDocument.AFTER,
                    projection={"version": 1},
                )
        else:
            updated_doc = self._col.find_one_and_update(
                filter={"blueprint_id": blueprint_id, "version": expected_version},
                update={
                    "$set": common_set,
                    "$inc": {"version": 1},
                },
                return_document=ReturnDocument.AFTER,
                projection={"version": 1},
            )

        if updated_doc is None:
            return None  # Not found or OCC conflict.

        return int(updated_doc["version"])

    def set_metadata(self, blueprint_id: str, metadata: dict) -> bool:
        now = datetime.now(timezone.utc)
        result = self._col.update_one(
            {"blueprint_id": blueprint_id},
            {"$set": {"metadata": metadata, "updated_at": now}},
        )
        return result.matched_count > 0

    def delete(self, blueprint_id: str) -> bool:
        result = self._col.delete_one({"blueprint_id": blueprint_id})
        return result.deleted_count > 0

    def delete_by_identity(self, identity: Identity) -> int:
        result = self._col.delete_many(
            {"identity.type": identity.type, "identity.id": identity.id}
        )
        return result.deleted_count

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def load(self, blueprint_id: str) -> BlueprintDocument:
        raw = self._col.find_one({"blueprint_id": blueprint_id})
        if raw is None:
            raise KeyError(f"Blueprint not found: {blueprint_id!r}")
        return self._doc_to_model(raw)

    def load_many(self, blueprint_ids: List[str]) -> List[BlueprintDocument]:
        cursor = self._col.find({"blueprint_id": {"$in": blueprint_ids}})
        return [self._doc_to_model(raw) for raw in cursor]

    def exists(self, blueprint_id: str) -> bool:
        return self._col.count_documents({"blueprint_id": blueprint_id}, limit=1) > 0

    def list_ids(
        self,
        identity: Optional[Identity] = None,
        skip: int = 0,
        limit: int = 20,
        sort_desc: bool = True,
    ) -> List[str]:
        flt = self._identity_filter(identity)
        direction = DESCENDING if sort_desc else 1
        cursor = (
            self._col.find(flt, {"blueprint_id": 1})
            .sort("created_at", direction)
            .skip(skip)
            .limit(limit)
        )
        return [doc["blueprint_id"] for doc in cursor]

    def list_docs(
        self,
        identity: Optional[Identity] = None,
        skip: int = 0,
        limit: int = 20,
        sort_desc: bool = True,
    ) -> List[BlueprintDocument]:
        flt = self._identity_filter(identity)
        direction = DESCENDING if sort_desc else 1
        cursor = (
            self._col.find(flt).sort("created_at", direction).skip(skip).limit(limit)
        )
        return [self._doc_to_model(raw) for raw in cursor]

    def list_summaries(
        self,
        identity: Optional[Identity] = None,
        skip: int = 0,
        limit: int = 20,
        sort_desc: bool = True,
    ) -> List[BlueprintSummary]:
        flt = self._identity_filter(identity)
        direction = DESCENDING if sort_desc else 1
        projection = {
            "blueprint_id": 1,
            "identity": 1,
            "created_at": 1,
            "updated_at": 1,
            "metadata": 1,
            "version": 1,
            # Extract name/description from spec_dict for the summary.
            "spec_dict.name": 1,
            "spec_dict.description": 1,
        }
        cursor = (
            self._col.find(flt, projection)
            .sort("created_at", direction)
            .skip(skip)
            .limit(limit)
        )
        summaries = []
        for raw in cursor:
            raw.setdefault("version", 1)
            spec = raw.get("spec_dict", {})
            summaries.append(
                BlueprintSummary(
                    blueprint_id=raw["blueprint_id"],
                    identity=Identity.model_validate(raw["identity"]),
                    name=spec.get("name", ""),
                    description=spec.get("description", ""),
                    created_at=raw.get("created_at"),
                    updated_at=raw.get("updated_at"),
                    metadata=raw.get("metadata", {}),
                    version=raw.get("version", 1),
                )
            )
        return summaries

    def count(self, identity: Optional[Identity] = None) -> int:
        return self._col.count_documents(self._identity_filter(identity))

    def list_direct_usage(self, rid: str) -> List[str]:
        cursor = self._col.find({"rid_refs": rid}, {"blueprint_id": 1})
        return [doc["blueprint_id"] for doc in cursor]

    def count_usage(self, rid: str) -> int:
        return self._col.count_documents({"rid_refs": rid})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _identity_filter(identity: Optional[Identity]) -> Dict[str, Any]:
        if identity is None:
            return {}
        return {"identity.type": identity.type, "identity.id": identity.id}

    @staticmethod
    def _doc_to_model(raw: Dict[str, Any]) -> BlueprintDocument:
        """
        Convert a raw MongoDB document to a ``BlueprintDocument``.

        Back-fills ``version = 1`` for documents that pre-date the
        GENIE-1336 migration (i.e. have no ``version`` field).
        """
        raw.setdefault("version", 1)
        # Remove the MongoDB internal _id to avoid Pydantic validation noise.
        raw.pop("_id", None)
        return BlueprintDocument.model_validate(raw)
