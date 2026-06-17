"""
MongoDB adapter for the blueprint version snapshot repository — GENIE-1336.

Implements :class:`mas.blueprints.repository.version_repository.BlueprintVersionRepository`
using synchronous pymongo, consistent with the rest of the adapters/outbound/mongo/ layer.

Collection: ``blueprint_versions`` (append-only, never updated or deleted in production).

Indexes (created idempotently on startup):
  - Unique compound: ``{ blueprint_id: 1, version: 1 }``
  - Non-unique:      ``{ blueprint_id: 1, created_at: -1 }``
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

import pymongo
from pymongo.collection import Collection

from global_utils.utils.util import get_mongo_url
from mas.blueprints.models.blueprint_version import BlueprintVersionDocument
from mas.blueprints.repository.version_repository import BlueprintVersionRepository


class MongoBlueprintVersionRepository(BlueprintVersionRepository):
    """Synchronous pymongo implementation of :class:`BlueprintVersionRepository`.

    The constructor creates the collection handle and ensures indexes are
    present, which is safe to call multiple times (idempotent).

    Args:
        db_name: MongoDB database name. Defaults to ``"UnifAI"``.
        coll_name: Collection name. Defaults to ``"blueprint_versions"``.
        col: Optional pre-wired :class:`pymongo.collection.Collection`.
            When provided, ``db_name`` and ``coll_name`` are ignored.
            **Inject this in tests** to avoid connecting to a real MongoDB.
    """

    def __init__(
        self,
        db_name: str = "UnifAI",
        coll_name: str = "blueprint_versions",
        col: Optional[Collection] = None,
    ) -> None:
        if col is not None:
            self._col: Collection = col
        else:
            mongo_uri = get_mongo_url()
            client = pymongo.MongoClient(mongo_uri)
            self._col = client[db_name][coll_name]
        self.ensure_indexes()

    # ── Infrastructure ────────────────────────────────────────────────────

    def ensure_indexes(self) -> None:
        """Create required indexes idempotently.  Safe to call on startup."""
        # Unique compound: prevents duplicate version numbers per blueprint.
        self._col.create_index(
            [("blueprint_id", pymongo.ASCENDING), ("version", pymongo.ASCENDING)],
            unique=True,
            name="idx_blueprint_version_unique",
            background=True,
        )
        # Non-unique: optimises paginated list queries sorted by recency.
        self._col.create_index(
            [("blueprint_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
            name="idx_blueprint_version_list",
            background=True,
        )

    # ── Writes ────────────────────────────────────────────────────────────

    def insert_snapshot(self, version_doc: BlueprintVersionDocument) -> str:
        """Persist an immutable version snapshot and return its ``_id``.

        Raises:
            pymongo.errors.DuplicateKeyError: If ``(blueprint_id, version)``
                already exists — the unique index guards against duplicates.
        """
        doc = {
            "blueprint_id": version_doc.blueprint_id,
            "version": version_doc.version,
            "spec_dict_snapshot": version_doc.spec_dict_snapshot,
            "created_by": version_doc.created_by,
            "created_at": version_doc.created_at,
            "change_summary": version_doc.change_summary,
        }
        result = self._col.insert_one(doc)
        return str(result.inserted_id)

    # ── Reads ─────────────────────────────────────────────────────────────

    def find_by_blueprint_id(
        self,
        blueprint_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[BlueprintVersionDocument], int]:
        """Return paginated version **summaries** for a blueprint (version DESC).

        ``spec_dict_snapshot`` is projected out to keep the response compact.
        """
        query = {"blueprint_id": blueprint_id}
        total_count: int = self._col.count_documents(query)

        skip = (page - 1) * page_size
        cursor = (
            self._col.find(
                query,
                # Projection: exclude the (potentially large) snapshot for list views.
                {"spec_dict_snapshot": 0},
            )
            .sort("version", pymongo.DESCENDING)
            .skip(skip)
            .limit(page_size)
        )

        versions: List[BlueprintVersionDocument] = []
        for doc in cursor:
            versions.append(
                BlueprintVersionDocument(
                    blueprint_id=doc["blueprint_id"],
                    version=doc["version"],
                    spec_dict_snapshot={},  # Not loaded in list view
                    created_by=doc["created_by"],
                    created_at=doc["created_at"],
                    change_summary=doc.get("change_summary"),
                    _id=str(doc["_id"]),
                )
            )
        return versions, total_count

    def find_one(
        self,
        blueprint_id: str,
        version: int,
    ) -> Optional[BlueprintVersionDocument]:
        """Load a specific version with the full ``spec_dict_snapshot``.

        Returns:
            :class:`BlueprintVersionDocument` (with full snapshot) or ``None``.
        """
        doc = self._col.find_one({"blueprint_id": blueprint_id, "version": version})
        if doc is None:
            return None
        return BlueprintVersionDocument(
            blueprint_id=doc["blueprint_id"],
            version=doc["version"],
            spec_dict_snapshot=doc["spec_dict_snapshot"],
            created_by=doc["created_by"],
            created_at=doc["created_at"],
            change_summary=doc.get("change_summary"),
            _id=str(doc["_id"]),
        )
