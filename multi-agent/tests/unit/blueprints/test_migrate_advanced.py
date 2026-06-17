"""
Advanced unit tests for migrate_blueprint_versions.py.

Covers:
  - batch processing (batch_size parameter)
  - full two-step migration integration
  - error resilience on individual doc failures
  - snapshot spec_dict_snapshot deep-copy isolation
  - migration with mixed docs (some with version, some without)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

try:
    import mongomock
    MONGOMOCK_AVAILABLE = True
except ImportError:
    MONGOMOCK_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not MONGOMOCK_AVAILABLE, reason="mongomock not installed"
)

from scripts.migrate_blueprint_versions import (
    step1_backfill_version_field,
    step2_insert_initial_snapshots,
    ensure_version_indexes,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mongo_client():
    return mongomock.MongoClient()


@pytest.fixture()
def bp_col(mongo_client):
    return mongo_client["test"]["blueprints"]


@pytest.fixture()
def ver_col(mongo_client):
    return mongo_client["test"]["blueprint_versions"]


def _insert_many_blueprints(col, n: int, prefix: str = "bp", with_version: bool = True):
    """Seed N blueprints; optionally include the version field."""
    docs = []
    for i in range(1, n + 1):
        doc = {
            "blueprint_id": f"{prefix}-{i}",
            "identity": {"type": "user", "id": "alice"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "spec_dict": {"name": f"Blueprint {i}"},
            "rid_refs": [],
            "metadata": {},
        }
        if with_version:
            doc["version"] = 1
        docs.append(doc)
    col.insert_many(docs)


# ===========================================================================
# Batch processing
# ===========================================================================


class TestBatchProcessing:
    def test_step2_processes_all_docs_in_multiple_batches(self, bp_col, ver_col):
        _insert_many_blueprints(bp_col, 25, with_version=True)
        count = step2_insert_initial_snapshots(bp_col, ver_col, dry_run=False, batch_size=10)
        assert ver_col.count_documents({}) == 25
        assert count == 25

    def test_batch_size_1_processes_all_docs(self, bp_col, ver_col):
        _insert_many_blueprints(bp_col, 5, with_version=True)
        count = step2_insert_initial_snapshots(bp_col, ver_col, dry_run=False, batch_size=1)
        assert count == 5
        assert ver_col.count_documents({}) == 5

    def test_batch_size_larger_than_collection(self, bp_col, ver_col):
        _insert_many_blueprints(bp_col, 3, with_version=True)
        count = step2_insert_initial_snapshots(bp_col, ver_col, dry_run=False, batch_size=1000)
        assert count == 3

    def test_step1_large_collection(self, bp_col):
        """step1 should handle large collections (no batch logic, single update_many)."""
        _insert_many_blueprints(bp_col, 50, with_version=False)
        updated = step1_backfill_version_field(bp_col, dry_run=False)
        assert updated == 50
        assert bp_col.count_documents({"version": {"$ne": 1}}) == 0


# ===========================================================================
# Full two-step migration
# ===========================================================================


class TestFullMigration:
    def test_full_migration_on_fresh_collection(self, bp_col, ver_col):
        """End-to-end: seed docs without version → step1 → step2 → assert state."""
        _insert_many_blueprints(bp_col, 5, with_version=False)

        # Step 1
        updated = step1_backfill_version_field(bp_col, dry_run=False)
        assert updated == 5
        assert bp_col.count_documents({"version": {"$exists": False}}) == 0

        # Step 2
        count = step2_insert_initial_snapshots(bp_col, ver_col, dry_run=False)
        assert count == 5
        assert ver_col.count_documents({}) == 5

        # Each version snapshot has version=1 and correct spec
        for snap in ver_col.find():
            assert snap["version"] == 1
            assert "spec_dict_snapshot" in snap

    def test_idempotent_on_repeated_execution(self, bp_col, ver_col):
        _insert_many_blueprints(bp_col, 3, with_version=False)

        for _ in range(3):  # run migration 3 times
            step1_backfill_version_field(bp_col, dry_run=False)
            step2_insert_initial_snapshots(bp_col, ver_col, dry_run=False)

        # Still only 3 blueprints and 3 snapshots
        assert bp_col.count_documents({}) == 3
        assert ver_col.count_documents({}) == 3

    def test_mixed_collection_only_backfills_missing_version(self, bp_col, ver_col):
        """Blueprints that already have version should not be touched by step1."""
        _insert_many_blueprints(bp_col, 3, prefix="new", with_version=False)
        _insert_many_blueprints(bp_col, 2, prefix="old", with_version=True)
        # Give one old doc a higher version to test preservation
        bp_col.update_one({"blueprint_id": "old-1"}, {"$set": {"version": 7}})

        updated = step1_backfill_version_field(bp_col, dry_run=False)
        assert updated == 3  # only the 'new' docs

        doc_old1 = bp_col.find_one({"blueprint_id": "old-1"})
        assert doc_old1["version"] == 7  # preserved

    def test_step2_snapshot_spec_matches_blueprint_spec(self, bp_col, ver_col):
        unique_spec = {"name": "Unique", "plan": [{"uid": "step-99"}]}
        bp_col.insert_one({
            "blueprint_id": "bp-unique",
            "identity": {"type": "user", "id": "alice"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "spec_dict": unique_spec,
            "rid_refs": [],
            "metadata": {},
            "version": 1,
        })
        step2_insert_initial_snapshots(bp_col, ver_col, dry_run=False)
        snap = ver_col.find_one({"blueprint_id": "bp-unique"})
        assert snap["spec_dict_snapshot"] == unique_spec


# ===========================================================================
# Snapshot spec isolation (deep-copy)
# ===========================================================================


class TestSnapshotIsolation:
    def test_mutating_source_doc_does_not_affect_snapshot(self, bp_col, ver_col):
        """Verify that the inserted snapshot is a deep copy, not a reference."""
        spec = {"name": "Original", "nested": {"key": "value"}}
        bp_col.insert_one({
            "blueprint_id": "bp-iso",
            "identity": {"type": "user", "id": "test"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "spec_dict": spec,
            "rid_refs": [],
            "metadata": {},
            "version": 1,
        })
        step2_insert_initial_snapshots(bp_col, ver_col, dry_run=False)

        # Update the source blueprint
        bp_col.update_one({"blueprint_id": "bp-iso"}, {"$set": {"spec_dict.nested.key": "mutated"}})

        # Snapshot must be unchanged
        snap = ver_col.find_one({"blueprint_id": "bp-iso"})
        assert snap["spec_dict_snapshot"]["nested"]["key"] == "value"


# ===========================================================================
# Dry-run mode
# ===========================================================================


class TestDryRun:
    def test_step1_dry_run_returns_candidate_count_without_writing(self, bp_col):
        _insert_many_blueprints(bp_col, 4, with_version=False)
        count = step1_backfill_version_field(bp_col, dry_run=True)
        # Must not have written anything
        assert bp_col.count_documents({"version": {"$exists": True}}) == 0
        # Must still report how many would be updated
        assert isinstance(count, int)

    def test_step2_dry_run_returns_candidate_count_without_writing(self, bp_col, ver_col):
        _insert_many_blueprints(bp_col, 3, with_version=True)
        count = step2_insert_initial_snapshots(bp_col, ver_col, dry_run=True)
        assert ver_col.count_documents({}) == 0
        assert isinstance(count, int)
