"""
Unit tests for MongoBlueprintVersionRepository — GENIE-1336.

All tests inject a mock ``pymongo.collection.Collection`` via the ``col=``
constructor kwarg (DFT hook) so no real MongoDB connection is needed.

Covers:
  - ensure_indexes() creates the two expected indexes
  - insert_snapshot() serialises the document correctly, returns string _id
  - find_by_blueprint_id() projects out snapshot, sorts DESC, paginates correctly
  - find_one() returns None on miss; returns full doc with snapshot on hit
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

from bson import ObjectId

from mas.blueprints.models.blueprint_version import BlueprintVersionDocument
from adapters.outbound.mongo.blueprint_version_repository import MongoBlueprintVersionRepository


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_repo(col: MagicMock) -> MongoBlueprintVersionRepository:
    """Create a repository wired to the given mock collection.

    ensure_indexes() is automatically called by __init__ so the mock
    must handle create_index calls.
    """
    return MongoBlueprintVersionRepository(col=col)


def _mongo_doc(
    blueprint_id: str = "bp-1",
    version: int = 1,
    spec_dict_snapshot: dict | None = None,
    created_by: str = "user",
    created_at: datetime | None = None,
    change_summary: str | None = None,
    _id: ObjectId | None = None,
) -> dict:
    """Construct a dict that looks like what pymongo returns from a .find_one() call."""
    return {
        "_id": _id or ObjectId(),
        "blueprint_id": blueprint_id,
        "version": version,
        "spec_dict_snapshot": spec_dict_snapshot or {},
        "created_by": created_by,
        "created_at": created_at or datetime(2025, 1, 1, tzinfo=timezone.utc),
        "change_summary": change_summary,
    }


# ── ensure_indexes ─────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestEnsureIndexes:
    """ensure_indexes() is called during __init__ and creates both indexes."""

    def test_creates_unique_compound_index(self):
        col = MagicMock()
        _make_repo(col)

        # Gather all create_index calls
        calls = col.create_index.call_args_list
        # At least one call should create the unique compound index
        unique_calls = [c for c in calls if c.kwargs.get("unique") is True]
        assert len(unique_calls) >= 1, "Expected a unique compound index to be created"

        # Verify the fields
        unique_call_keys = [c.args[0] for c in unique_calls]
        assert any(
            [("blueprint_id", 1), ("version", 1)] == list(keys)
            for keys in unique_call_keys
        )

    def test_creates_list_index(self):
        col = MagicMock()
        _make_repo(col)

        calls = col.create_index.call_args_list
        # There should be a non-unique index on (blueprint_id, created_at DESC)
        non_unique_calls = [c for c in calls if not c.kwargs.get("unique")]
        assert len(non_unique_calls) >= 1, "Expected a non-unique list index"

    def test_indexes_created_exactly_twice_on_init(self):
        col = MagicMock()
        _make_repo(col)
        assert col.create_index.call_count == 2


# ── insert_snapshot ────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestInsertSnapshot:
    """insert_snapshot() serialises the document and returns the inserted _id."""

    def _repo_and_inserted_id(self) -> tuple[MongoBlueprintVersionRepository, ObjectId, MagicMock]:
        oid = ObjectId()
        col = MagicMock()
        col.insert_one.return_value.inserted_id = oid
        return _make_repo(col), oid, col

    def test_returns_string_id(self):
        repo, oid, _ = self._repo_and_inserted_id()
        doc = BlueprintVersionDocument(
            blueprint_id="bp-1", version=3, spec_dict_snapshot={"a": 1}, created_by="u"
        )
        result = repo.insert_snapshot(doc)
        assert result == str(oid)

    def test_passes_correct_fields_to_insert_one(self):
        repo, _, col = self._repo_and_inserted_id()
        ts = datetime(2025, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        doc = BlueprintVersionDocument(
            blueprint_id="bp-42",
            version=7,
            spec_dict_snapshot={"nodes": []},
            created_by="alice",
            created_at=ts,
            change_summary="Initial",
        )
        repo.insert_snapshot(doc)

        col.insert_one.assert_called_once()
        persisted = col.insert_one.call_args.args[0]

        assert persisted["blueprint_id"] == "bp-42"
        assert persisted["version"] == 7
        assert persisted["spec_dict_snapshot"] == {"nodes": []}
        assert persisted["created_by"] == "alice"
        assert persisted["created_at"] == ts
        assert persisted["change_summary"] == "Initial"
        # _id must NOT be in the payload (MongoDB generates it)
        assert "_id" not in persisted

    def test_does_not_mutate_document_snapshot(self):
        """The snapshot inside the doc object is untouched after insert."""
        repo, _, _ = self._repo_and_inserted_id()
        original_spec = {"k": "v"}
        doc = BlueprintVersionDocument(
            blueprint_id="bp-1", version=1, spec_dict_snapshot=original_spec, created_by="u"
        )
        repo.insert_snapshot(doc)
        assert doc.spec_dict_snapshot == {"k": "v"}


# ── find_by_blueprint_id ───────────────────────────────────────────────────────


@pytest.mark.unit
class TestFindByBlueprintId:
    """find_by_blueprint_id() paginates correctly and excludes the snapshot."""

    def _col_with_cursor(self, docs: list, total: int) -> MagicMock:
        """Return a mock Collection whose .find(...).sort(...).skip(...).limit(...) chain yields *docs*."""
        col = MagicMock()
        col.count_documents.return_value = total

        cursor = MagicMock()
        cursor.__iter__ = MagicMock(return_value=iter(docs))
        # Chain: find(...) → sort(...) → skip(...) → limit(...)
        col.find.return_value.sort.return_value.skip.return_value.limit.return_value = cursor
        return col

    def test_returns_items_and_total(self):
        raw_docs = [
            _mongo_doc(blueprint_id="bp-1", version=2),
            _mongo_doc(blueprint_id="bp-1", version=1),
        ]
        col = self._col_with_cursor(raw_docs, total=2)
        repo = _make_repo(col)

        items, total = repo.find_by_blueprint_id("bp-1", page=1, page_size=20)

        assert total == 2
        assert len(items) == 2
        assert items[0].version == 2
        assert items[1].version == 1

    def test_projects_out_spec_dict_snapshot(self):
        """The projection sent to pymongo must exclude spec_dict_snapshot."""
        col = self._col_with_cursor([], total=0)
        repo = _make_repo(col)
        repo.find_by_blueprint_id("bp-1", page=1, page_size=20)

        find_call = col.find.call_args
        projection = find_call.args[1] if len(find_call.args) > 1 else find_call.kwargs.get("projection")
        assert projection is not None
        assert projection.get("spec_dict_snapshot") == 0

    def test_snapshot_field_is_empty_dict_in_list_view(self):
        """Items returned from find_by_blueprint_id have spec_dict_snapshot={}."""
        raw_docs = [_mongo_doc(blueprint_id="bp-1", version=1)]
        col = self._col_with_cursor(raw_docs, total=1)
        repo = _make_repo(col)

        items, _ = repo.find_by_blueprint_id("bp-1", page=1, page_size=20)
        assert items[0].spec_dict_snapshot == {}

    def test_pagination_skip_and_limit(self):
        """Page 2 of page_size 5 must call skip(5).limit(5)."""
        col = self._col_with_cursor([], total=10)
        repo = _make_repo(col)
        repo.find_by_blueprint_id("bp-1", page=2, page_size=5)

        sort_chain = col.find.return_value.sort.return_value
        sort_chain.skip.assert_called_once_with(5)
        sort_chain.skip.return_value.limit.assert_called_once_with(5)

    def test_sort_is_version_descending(self):
        import pymongo as pm
        col = self._col_with_cursor([], total=0)
        repo = _make_repo(col)
        repo.find_by_blueprint_id("bp-1", page=1, page_size=20)

        find_result = col.find.return_value
        find_result.sort.assert_called_once_with("version", pm.DESCENDING)

    def test_returned_items_have_correct_blueprint_id_and_created_by(self):
        ts = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        raw_docs = [
            _mongo_doc(blueprint_id="bp-X", version=5, created_by="carol", created_at=ts)
        ]
        col = self._col_with_cursor(raw_docs, total=1)
        repo = _make_repo(col)

        items, _ = repo.find_by_blueprint_id("bp-X")
        assert items[0].blueprint_id == "bp-X"
        assert items[0].created_by == "carol"
        assert items[0].created_at == ts
        assert items[0]._id is not None  # String ObjectId

    def test_empty_result(self):
        col = self._col_with_cursor([], total=0)
        repo = _make_repo(col)

        items, total = repo.find_by_blueprint_id("nonexistent")
        assert items == []
        assert total == 0


# ── find_one ──────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestFindOne:
    """find_one() returns None on miss and a full BlueprintVersionDocument on hit."""

    def test_returns_none_when_not_found(self):
        col = MagicMock()
        col.find_one.return_value = None
        repo = _make_repo(col)

        result = repo.find_one("bp-1", 99)
        assert result is None
        col.find_one.assert_called_once_with({"blueprint_id": "bp-1", "version": 99})

    def test_returns_document_with_full_snapshot(self):
        snapshot = {"nodes": [{"id": "n1"}], "edges": []}
        raw = _mongo_doc(blueprint_id="bp-7", version=3, spec_dict_snapshot=snapshot)
        col = MagicMock()
        col.find_one.return_value = raw
        repo = _make_repo(col)

        result = repo.find_one("bp-7", 3)

        assert result is not None
        assert isinstance(result, BlueprintVersionDocument)
        assert result.blueprint_id == "bp-7"
        assert result.version == 3
        assert result.spec_dict_snapshot == snapshot

    def test_returned_document_id_is_string(self):
        oid = ObjectId()
        raw = _mongo_doc(_id=oid)
        col = MagicMock()
        col.find_one.return_value = raw
        repo = _make_repo(col)

        result = repo.find_one("bp-1", 1)
        assert result._id == str(oid)
        assert isinstance(result._id, str)

    def test_queries_by_blueprint_id_and_version(self):
        col = MagicMock()
        col.find_one.return_value = None
        repo = _make_repo(col)

        repo.find_one("my-blueprint", 42)
        col.find_one.assert_called_once_with({"blueprint_id": "my-blueprint", "version": 42})

    def test_change_summary_none_when_absent(self):
        raw = _mongo_doc(change_summary=None)
        col = MagicMock()
        col.find_one.return_value = raw
        repo = _make_repo(col)

        result = repo.find_one("bp-1", 1)
        assert result.change_summary is None
