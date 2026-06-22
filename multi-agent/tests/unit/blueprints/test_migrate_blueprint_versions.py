"""
Unit tests for the ``_migrate()`` function in
``run/scripts/migrate_blueprint_versions.py`` — GENIE-1336.

All MongoDB calls are intercepted via ``MagicMock`` objects so no real DB
connection is needed.

Covers:
  - Happy path: sets version=1 on legacy docs, inserts initial snapshots
  - Idempotency: docs that already have ``version`` set are skipped in Step 1
  - Snapshot skip: docs whose blueprint_id is in ``existing_v1`` get no snapshot
  - Dry-run: no ``bulk_write`` / ``insert_one`` calls are made
  - BulkWriteError handling: partial failure is counted; function still returns
    the error count without re-raising
  - _batch() helper produces correct chunks
  - Return value: 0 on clean run, >0 on errors
"""

from __future__ import annotations

import sys
import os
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call
from pymongo.errors import BulkWriteError

# Ensure the scripts directory is importable.
_SCRIPTS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "run", "scripts"
)
sys.path.insert(0, os.path.abspath(_SCRIPTS_DIR))

from migrate_blueprint_versions import _migrate, _batch  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_blueprint(blueprint_id: str, version: int | None = None) -> dict:
    """Construct a minimal blueprint document dict as pymongo would return."""
    doc = {
        "blueprint_id": blueprint_id,
        "spec_dict": {"name": blueprint_id, "nodes": []},
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    if version is not None:
        doc["version"] = version
    return doc


def _mock_blueprints_col(docs: list) -> MagicMock:
    """Return a mock blueprints collection whose .find() yields *docs*."""
    col = MagicMock()
    col.count_documents.return_value = len(docs)
    # .find(...).batch_size(N) must return an iterable of docs.
    col.find.return_value.batch_size.return_value = iter(docs)
    return col


def _mock_versions_col(existing_v1_ids: list[str] | None = None) -> MagicMock:
    """Return a mock versions collection.

    ``existing_v1_ids`` — blueprint_ids that already have a version-1 snapshot.
    """
    col = MagicMock()
    existing_v1_ids = existing_v1_ids or []
    col.find.return_value = [{"blueprint_id": bid} for bid in existing_v1_ids]
    return col


# ── _batch() helper ────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestBatchHelper:
    """_batch() splits an iterable into fixed-size chunks."""

    def test_exact_multiple_of_batch_size(self):
        result = list(_batch([1, 2, 3, 4], 2))
        assert result == [[1, 2], [3, 4]]

    def test_remainder_in_last_chunk(self):
        result = list(_batch([1, 2, 3, 4, 5], 2))
        assert result == [[1, 2], [3, 4], [5]]

    def test_empty_iterable(self):
        assert list(_batch([], 10)) == []

    def test_batch_larger_than_iterable(self):
        result = list(_batch([1, 2, 3], 100))
        assert result == [[1, 2, 3]]

    def test_single_element_batches(self):
        result = list(_batch([10, 20, 30], 1))
        assert result == [[10], [20], [30]]


# ── Happy path ────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestMigrateHappyPath:
    """_migrate() correctly processes blueprints that need both steps."""

    def test_returns_zero_on_success(self):
        blueprints_col = _mock_blueprints_col([_make_blueprint("bp-1")])
        versions_col = _mock_versions_col()

        errors = _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        assert errors == 0

    def test_step1_bulk_write_called_for_versionless_doc(self):
        """A doc without 'version' triggers a $set version=1 bulk_write."""
        doc = _make_blueprint("bp-no-version")  # No version key.
        blueprints_col = _mock_blueprints_col([doc])
        versions_col = _mock_versions_col()

        _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        blueprints_col.bulk_write.assert_called_once()

    def test_step2_versions_bulk_write_called_for_new_snapshot(self):
        """A doc without an existing v1 snapshot triggers a version bulk_write."""
        doc = _make_blueprint("bp-no-snapshot")
        blueprints_col = _mock_blueprints_col([doc])
        versions_col = _mock_versions_col(existing_v1_ids=[])  # No existing snapshots.

        _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        versions_col.bulk_write.assert_called_once()

    def test_created_by_set_to_migration_user(self):
        """The snapshot created_by field is '_MIGRATION_USER'."""
        from migrate_blueprint_versions import _MIGRATION_USER

        doc = _make_blueprint("bp-1")
        blueprints_col = _mock_blueprints_col([doc])
        versions_col = _mock_versions_col()

        _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        # Inspect the UpdateOne operation passed to versions_col.bulk_write
        bulk_call_args = versions_col.bulk_write.call_args.args[0]
        # Each op is an UpdateOne; its _filter and _doc are in private attrs.
        set_on_insert = bulk_call_args[0]._doc["$setOnInsert"]
        assert set_on_insert["created_by"] == _MIGRATION_USER

    def test_change_summary_set_correctly(self):
        """The snapshot change_summary is the migration constant."""
        from migrate_blueprint_versions import _CHANGE_SUMMARY

        doc = _make_blueprint("bp-1")
        blueprints_col = _mock_blueprints_col([doc])
        versions_col = _mock_versions_col()

        _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        bulk_call_args = versions_col.bulk_write.call_args.args[0]
        set_on_insert = bulk_call_args[0]._doc["$setOnInsert"]
        assert set_on_insert["change_summary"] == _CHANGE_SUMMARY

    def test_snapshot_version_is_always_1(self):
        """The initial snapshot is always version=1 regardless of doc state."""
        doc = _make_blueprint("bp-existing", version=1)
        blueprints_col = _mock_blueprints_col([doc])
        versions_col = _mock_versions_col(existing_v1_ids=[])

        _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        bulk_call_args = versions_col.bulk_write.call_args.args[0]
        # The upsert filter must query for version=1
        filter_doc = bulk_call_args[0]._filter
        assert filter_doc["version"] == 1


# ── Idempotency ───────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestMigrateIdempotency:
    """Documents that already have version set or snapshots are skipped."""

    def test_step1_skipped_when_version_already_set(self):
        """A doc with version=1 is NOT included in the Step-1 bulk_write."""
        doc = _make_blueprint("bp-already-versioned", version=1)
        blueprints_col = _mock_blueprints_col([doc])
        versions_col = _mock_versions_col()

        _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        # blueprints_col.bulk_write should NOT be called (no docs need version set).
        blueprints_col.bulk_write.assert_not_called()

    def test_step2_skipped_when_snapshot_already_exists(self):
        """A blueprint that already has a v1 snapshot gets no new snapshot."""
        doc = _make_blueprint("bp-has-snapshot", version=1)
        blueprints_col = _mock_blueprints_col([doc])
        # This blueprint already has a v1 snapshot.
        versions_col = _mock_versions_col(existing_v1_ids=["bp-has-snapshot"])

        _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        # No new snapshots — versions_col.bulk_write must not be called.
        versions_col.bulk_write.assert_not_called()

    def test_all_docs_already_migrated_no_writes(self):
        """When everything is already migrated, zero DB writes are performed."""
        docs = [
            _make_blueprint("bp-1", version=1),
            _make_blueprint("bp-2", version=3),
        ]
        blueprints_col = _mock_blueprints_col(docs)
        versions_col = _mock_versions_col(existing_v1_ids=["bp-1", "bp-2"])

        errors = _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        assert errors == 0
        blueprints_col.bulk_write.assert_not_called()
        versions_col.bulk_write.assert_not_called()

    def test_second_run_produces_no_extra_writes(self):
        """Simulates a second migration run — expects no writes."""
        doc = _make_blueprint("bp-1", version=1)
        blueprints_col = _mock_blueprints_col([doc])
        # First run would have created the snapshot; second run sees it.
        versions_col = _mock_versions_col(existing_v1_ids=["bp-1"])

        errors = _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        assert errors == 0
        blueprints_col.bulk_write.assert_not_called()
        versions_col.bulk_write.assert_not_called()


# ── Dry-run mode ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestMigrateDryRun:
    """When dry_run=True, no writes must reach MongoDB."""

    def test_blueprints_bulk_write_not_called(self):
        doc = _make_blueprint("bp-no-version")  # Would need step-1 update.
        blueprints_col = _mock_blueprints_col([doc])
        versions_col = _mock_versions_col()

        _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=True,
        )

        blueprints_col.bulk_write.assert_not_called()

    def test_versions_bulk_write_not_called(self):
        doc = _make_blueprint("bp-1")  # Would need step-2 snapshot.
        blueprints_col = _mock_blueprints_col([doc])
        versions_col = _mock_versions_col()

        _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=True,
        )

        versions_col.bulk_write.assert_not_called()

    def test_returns_zero_on_dry_run(self):
        """Dry-run is always clean — no errors."""
        blueprints_col = _mock_blueprints_col([_make_blueprint("bp-1")])
        versions_col = _mock_versions_col()

        errors = _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=True,
        )

        assert errors == 0

    def test_dry_run_on_empty_collection_returns_zero(self):
        blueprints_col = _mock_blueprints_col([])
        versions_col = _mock_versions_col()

        errors = _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=True,
        )

        assert errors == 0


# ── BulkWriteError handling ───────────────────────────────────────────────────


@pytest.mark.unit
class TestMigrateBulkWriteError:
    """Partial BulkWriteError is counted but does not abort the migration."""

    def test_returns_nonzero_error_count_on_bulk_write_error(self):
        doc = _make_blueprint("bp-1")
        blueprints_col = _mock_blueprints_col([doc])
        versions_col = _mock_versions_col()

        # Simulate 2 write errors in the batch.
        error_details = {"writeErrors": [{"code": 11000}, {"code": 11000}]}
        versions_col.bulk_write.side_effect = BulkWriteError(error_details)

        errors = _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        assert errors == 2

    def test_does_not_raise_on_bulk_write_error(self):
        """BulkWriteError is caught internally; _migrate() must not propagate it."""
        doc = _make_blueprint("bp-1")
        blueprints_col = _mock_blueprints_col([doc])
        versions_col = _mock_versions_col()
        versions_col.bulk_write.side_effect = BulkWriteError({"writeErrors": [{"code": 11000}]})

        # Must not raise.
        try:
            _migrate(
                blueprints_col=blueprints_col,
                versions_col=versions_col,
                batch_size=100,
                dry_run=False,
            )
        except BulkWriteError:
            pytest.fail("_migrate() should not propagate BulkWriteError")

    def test_continues_processing_remaining_batches_after_error(self):
        """Even after a BulkWriteError in batch N, subsequent batches are processed."""
        docs = [_make_blueprint(f"bp-{i}") for i in range(6)]
        blueprints_col = _mock_blueprints_col(docs)
        versions_col = _mock_versions_col()

        # Only the first call to bulk_write raises; subsequent calls succeed.
        call_count = {"n": 0}
        original_side_effect = BulkWriteError({"writeErrors": [{"code": 11000}]})

        def _side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise original_side_effect
            return MagicMock()

        versions_col.bulk_write.side_effect = _side_effect

        errors = _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=3,
            dry_run=False,
        )

        # First batch had 1 error; second batch succeeded.
        assert errors == 1
        assert versions_col.bulk_write.call_count == 2


# ── Edge cases ────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestMigrateEdgeCases:
    """Edge-case behaviours."""

    def test_empty_blueprints_collection_returns_zero(self):
        blueprints_col = _mock_blueprints_col([])
        versions_col = _mock_versions_col()

        errors = _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        assert errors == 0
        blueprints_col.bulk_write.assert_not_called()
        versions_col.bulk_write.assert_not_called()

    def test_blueprint_with_no_spec_dict_gets_empty_snapshot(self):
        """A doc with no spec_dict defaults the snapshot to {}."""
        doc = {"blueprint_id": "bp-empty-spec", "created_at": datetime.now(timezone.utc)}
        blueprints_col = _mock_blueprints_col([doc])
        versions_col = _mock_versions_col()

        _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        bulk_call_args = versions_col.bulk_write.call_args.args[0]
        set_on_insert = bulk_call_args[0]._doc["$setOnInsert"]
        assert set_on_insert["spec_dict_snapshot"] == {}

    def test_blueprint_created_at_is_preserved_in_snapshot(self):
        """The blueprint's created_at is used as the snapshot created_at."""
        ts = datetime(2024, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
        doc = _make_blueprint("bp-ts")
        doc["created_at"] = ts
        blueprints_col = _mock_blueprints_col([doc])
        versions_col = _mock_versions_col()

        _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        bulk_call_args = versions_col.bulk_write.call_args.args[0]
        set_on_insert = bulk_call_args[0]._doc["$setOnInsert"]
        assert set_on_insert["created_at"] == ts

    def test_batch_size_respected_in_cursor_batching(self):
        """The blueprints cursor is queried with the configured batch_size."""
        docs = [_make_blueprint(f"bp-{i}") for i in range(10)]
        blueprints_col = _mock_blueprints_col(docs)
        versions_col = _mock_versions_col()

        _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=5,
            dry_run=False,
        )

        blueprints_col.find.return_value.batch_size.assert_called_once_with(5)

    def test_mixed_bag_partial_migration_needed(self):
        """With some docs already migrated and some not, only the unmigratable ones are skipped."""
        docs = [
            _make_blueprint("bp-needs-version"),       # No version, no snapshot
            _make_blueprint("bp-has-version", version=2),  # Has version, no snapshot
        ]
        blueprints_col = _mock_blueprints_col(docs)
        versions_col = _mock_versions_col(existing_v1_ids=[])

        _migrate(
            blueprints_col=blueprints_col,
            versions_col=versions_col,
            batch_size=100,
            dry_run=False,
        )

        # Step 1: only bp-needs-version gets version=1
        blueprints_col.bulk_write.assert_called_once()
        # Step 2: both blueprints need a snapshot (neither has one)
        versions_col.bulk_write.assert_called_once()
        ops = versions_col.bulk_write.call_args.args[0]
        assert len(ops) == 2
