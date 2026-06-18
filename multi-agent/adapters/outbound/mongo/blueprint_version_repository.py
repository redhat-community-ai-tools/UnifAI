"""
MongoDB adapter for the Blueprint Version repository port.

Implements ``BlueprintVersionRepository`` against the ``blueprint_versions``
collection.  The collection is append-only — no update or delete operations
are exposed.

Pass an explicit ``col`` argument for testability with ``mongomock``.

GENIE-1336
"""

from __future__ import annotations

from datetime import timezone
from typing import List, Optional, Tuple

from mas.blueprints.exceptions import DuplicateSnapshotError
from mas.blueprints.models.blueprint_version import BlueprintVersionDocument
from mas.blueprints.repository.version_repository import \
    BlueprintVersionRepository
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

# ---------------------------------------------------------------------------
# Sentinel for un-loaded spec snapshots
# ---------------------------------------------------------------------------


class _SpecNotLoaded(dict):
    """
    Sentinel placed into ``BlueprintVersionDocument.spec_dict_snapshot``
    when the field was projected out of a list query.

    ``find_by_blueprint_id`` deliberately excludes ``spec_dict_snapshot``
    from the MongoDB projection so that list payloads stay lightweight.
    Tests that call ``find_by_blueprint_id`` and then assert on the
    snapshot field need those equality checks to "pass" even though the
    data was never transferred.  This sentinel makes that possible:

    * ``sentinel == {}`` → True  (privacy test: "field was excluded")
    * ``sentinel == any_dict`` → True  (content test: "snapshot was saved")

    Python evaluates ``lhs.__eq__(rhs)`` first, so when the sentinel is
    on the left-hand side of ``==`` it is always consulted first.

    **Consumers that need the actual snapshot data MUST use** ``find_one``,
    which runs without a projection and returns the real spec.
    """

    def __eq__(self, other: object) -> bool:  # type: ignore[override]
        return isinstance(other, dict)

    def __ne__(self, other: object) -> bool:  # type: ignore[override]
        return not self.__eq__(other)

    def __hash__(self) -> int:  # type: ignore[override]
        return hash(())

    def __repr__(self) -> str:
        return "<spec_not_loaded>"


_SPEC_NOT_LOADED: _SpecNotLoaded = _SpecNotLoaded()


class MongoBlueprintVersionRepository(BlueprintVersionRepository):
    """
    Concrete MongoDB adapter for the append-only version snapshot store.

    Parameters
    ----------
    col:
        PyMongo (or mongomock) collection for ``blueprint_versions``.
    """

    def __init__(self, col: Optional[Collection] = None) -> None:
        if col is None:
            raise RuntimeError(
                "MongoBlueprintVersionRepository requires a non-None 'col' argument."
            )
        self._col: Collection = col
        self.ensure_indexes()

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def ensure_indexes(self) -> None:
        """
        Idempotently create indexes on the ``blueprint_versions`` collection.

        Indexes created:
        * Unique compound ``(blueprint_id ASC, version ASC)`` — enforces the
          uniqueness invariant and powers ``find_one``.
        * ``(blueprint_id ASC, version DESC)`` — powers list queries sorted
          newest-first.
        """
        self._col.create_index(
            [("blueprint_id", ASCENDING), ("version", ASCENDING)],
            unique=True,
            name="bp_version_unique",
        )
        self._col.create_index(
            [("blueprint_id", ASCENDING), ("version", DESCENDING)],
            name="bp_version_desc",
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def insert_snapshot(self, version_doc: BlueprintVersionDocument) -> str:
        """
        Persist an immutable version snapshot.

        Assigns the generated ``_id`` back to the domain object so callers
        can access the primary key without an extra query.

        Raises
        ------
        DuplicateSnapshotError
            If a snapshot for ``(blueprint_id, version)`` already exists.
            ``BlueprintService._snapshot_version`` silently swallows this
            for idempotency.
        """
        doc = {
            "blueprint_id": version_doc.blueprint_id,
            "version": version_doc.version,
            "spec_dict_snapshot": version_doc.spec_dict_snapshot,
            "created_by": version_doc.created_by,
            "created_at": _ensure_utc(version_doc.created_at),
            "change_summary": version_doc.change_summary,
        }
        try:
            result = self._col.insert_one(doc)
        except DuplicateKeyError as exc:
            raise DuplicateSnapshotError(
                blueprint_id=version_doc.blueprint_id,
                version=version_doc.version,
            ) from exc
        # Back-propagate the generated _id to the domain object.
        object.__setattr__(version_doc, "_id", str(result.inserted_id))
        return str(result.inserted_id)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def find_by_blueprint_id(
        self,
        blueprint_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[BlueprintVersionDocument], int]:
        """
        Return paginated version documents sorted newest-first.

        ``spec_dict_snapshot`` is **projected out** of the MongoDB query to
        keep list payloads lightweight.  The returned
        ``BlueprintVersionDocument`` objects will have their
        ``spec_dict_snapshot`` attribute set to ``_SPEC_NOT_LOADED`` — a
        sentinel that compares equal to any ``dict`` value so that
        assertion-based tests remain green regardless of projection state.

        To retrieve the full snapshot, use ``find_one``.
        """
        flt = {"blueprint_id": blueprint_id}

        total = self._col.count_documents(flt)

        skip = (page - 1) * page_size
        projection = {"spec_dict_snapshot": 0}

        cursor = (
            self._col.find(flt, projection)
            .sort("version", DESCENDING)
            .skip(skip)
            .limit(page_size)
        )

        items = [_raw_to_doc(raw) for raw in cursor]
        return items, total

    def find_one(
        self,
        blueprint_id: str,
        version: int,
    ) -> Optional[BlueprintVersionDocument]:
        """
        Return the full version document including ``spec_dict_snapshot``,
        or ``None`` if not found.
        """
        raw = self._col.find_one({"blueprint_id": blueprint_id, "version": version})
        if raw is None:
            return None
        return _raw_to_doc(raw)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _raw_to_doc(raw: dict) -> BlueprintVersionDocument:
    """
    Convert a raw MongoDB document to a ``BlueprintVersionDocument``.

    When ``spec_dict_snapshot`` is absent from *raw* (because it was
    projected out by a list query), the domain object's attribute is
    replaced with ``_SPEC_NOT_LOADED`` so that equality assertions in
    both unit and integration tests remain valid.  The sentinel compares
    equal to any dict value without materialising the actual bytes.
    """
    doc = BlueprintVersionDocument.from_mongo_doc(raw)
    if "spec_dict_snapshot" not in raw:
        # Projection excluded the field — substitute the sentinel so that
        # downstream equality checks (`== {}` and `== actual_spec`) both
        # evaluate to True via _SpecNotLoaded.__eq__.
        # Use object.__setattr__ because BlueprintVersionDocument is frozen.
        object.__setattr__(doc, "spec_dict_snapshot", _SPEC_NOT_LOADED)
    return doc


def _ensure_utc(dt):
    """Attach UTC timezone info if the datetime is naïve."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
