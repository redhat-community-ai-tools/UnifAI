"""
Regression tests for Blueprint Versioning (GENIE-1336).

These tests verify the end-to-end vertical slice: Service → Repository →
MongoDB, using mongomock.  They guard against regressions in the most
critical user-facing behaviours.

Each test class isolates one user journey.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

try:
    import mongomock
    MONGOMOCK_AVAILABLE = True
except ImportError:
    MONGOMOCK_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not MONGOMOCK_AVAILABLE, reason="mongomock not installed"
)

from adapters.outbound.mongo.blueprint_repository import MongoBlueprintRepository
from adapters.outbound.mongo.blueprint_version_repository import (
    MongoBlueprintVersionRepository,
)
from mas.blueprints.exceptions import (
    BlueprintNotFoundError,
    ConcurrentModificationError,
    VersionNotFoundError,
)
from lib.mas.blueprints.models.blueprint import Identity
from lib.mas.blueprints.service import BlueprintService


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


@pytest.fixture()
def bp_repo(bp_col):
    return MongoBlueprintRepository(col=bp_col)


@pytest.fixture()
def ver_repo(ver_col):
    r = MongoBlueprintVersionRepository(col=ver_col)
    r.ensure_indexes()
    return r


@pytest.fixture()
def service(bp_repo, ver_repo):
    return BlueprintService(repo=bp_repo, version_repo=ver_repo)


@pytest.fixture()
def identity():
    return Identity(type="user", id="u-alice")


@pytest.fixture()
def blueprint_id(service, identity):
    """Create a blueprint and return its ID."""
    return service.create_draft(
        identity=identity,
        draft_dict={"name": "Initial Blueprint", "plan": []},
        user_id="u:alice",
    )


# ===========================================================================
# R01: version increments correctly through multiple edits
# ===========================================================================


class TestVersionIncrements:
    def test_initial_version_is_1(self, service, identity, bp_repo):
        bid = service.create_draft(
            identity=identity,
            draft_dict={"name": "V1"},
        )
        doc = bp_repo.load(bid)
        assert doc.version == 1

    def test_version_increments_on_each_update(self, service, blueprint_id, bp_repo):
        for expected_version in [2, 3, 4]:
            service.update_draft(blueprint_id, {"name": f"V{expected_version}"})
            doc = bp_repo.load(blueprint_id)
            assert doc.version == expected_version

    def test_version_history_length_matches_edit_count(self, service, blueprint_id, ver_repo):
        for i in range(3):
            service.update_draft(blueprint_id, {"name": f"Edit {i}"})
        _, total = ver_repo.find_by_blueprint_id(blueprint_id)
        assert total == 3  # snapshots at v1, v2, v3


# ===========================================================================
# R02: snapshot content matches pre-update spec
# ===========================================================================


class TestSnapshotContent:
    def test_snapshot_captures_pre_update_spec(self, service, identity, ver_repo):
        old_spec = {"name": "Before Edit", "plan": []}
        bid = service.create_draft(identity=identity, draft_dict=old_spec)
        new_spec = {"name": "After Edit", "plan": [{"uid": "s1"}]}
        service.update_draft(bid, new_spec)

        items, _ = ver_repo.find_by_blueprint_id(bid)
        # Newest snapshot is the v1 → taken before the update to v2
        assert items[0].spec_dict_snapshot == old_spec

    def test_snapshot_spec_is_independent_of_live_doc(self, service, identity, bp_repo, ver_repo):
        spec = {"name": "Snap", "nodes": [{"uid": "n1"}]}
        bid = service.create_draft(identity=identity, draft_dict=spec)
        service.update_draft(bid, {"name": "Changed", "nodes": []})

        # Live doc
        live = bp_repo.load(bid)
        assert live.spec_dict == {"name": "Changed", "nodes": []}

        # Snapshot must still hold original
        items, _ = ver_repo.find_by_blueprint_id(bid)
        assert items[0].spec_dict_snapshot == spec


# ===========================================================================
# R03: load_version returns correct snapshot
# ===========================================================================


class TestLoadVersionRegression:
    def test_load_version_returns_snapshot_at_requested_version(
        self, service, identity, ver_repo
    ):
        bid = service.create_draft(identity=identity, draft_dict={"name": "V1"})
        service.update_draft(bid, {"name": "V2"})
        service.update_draft(bid, {"name": "V3"})

        detail_v1 = service.load_version(bid, 1)
        assert detail_v1["spec_dict_snapshot"]["name"] == "V1"

        detail_v2 = service.load_version(bid, 2)
        assert detail_v2["spec_dict_snapshot"]["name"] == "V2"

    def test_load_version_raises_for_nonexistent_version(self, service, blueprint_id):
        with pytest.raises(VersionNotFoundError):
            service.load_version(blueprint_id, 9999)

    def test_load_version_raises_for_nonexistent_blueprint(self, service):
        with pytest.raises(BlueprintNotFoundError):
            service.load_version("nonexistent-bp", 1)


# ===========================================================================
# R04: restore_version rolls back live spec
# ===========================================================================


class TestRestoreVersionRegression:
    def test_restore_rolls_back_spec(self, service, identity, bp_repo):
        old_spec = {"name": "Original Plan", "plan": [{"uid": "s0"}]}
        bid = service.create_draft(identity=identity, draft_dict=old_spec)
        service.update_draft(bid, {"name": "Modified", "plan": []})

        service.restore_version(bid, target_version=1, user_id="u:alice")

        live = bp_repo.load(bid)
        assert live.spec_dict == old_spec

    def test_restore_creates_snapshot_before_overwrite(self, service, identity, ver_repo):
        bid = service.create_draft(identity=identity, draft_dict={"name": "V1"})
        service.update_draft(bid, {"name": "V2"})
        # At this point: v1 snapshot exists, live is v2
        service.restore_version(bid, target_version=1)
        # Should now have snapshots: v1 (from first edit) and v2 (from restore)
        _, total = ver_repo.find_by_blueprint_id(bid)
        assert total == 2

    def test_restore_version_not_found_raises(self, service, blueprint_id):
        with pytest.raises(VersionNotFoundError):
            service.restore_version(blueprint_id, target_version=999)

    def test_restore_on_missing_blueprint_raises(self, service):
        with pytest.raises(BlueprintNotFoundError):
            service.restore_version("ghost-bp", target_version=1)


# ===========================================================================
# R05: OCC prevents lost updates
# ===========================================================================


class TestOCCRegression:
    def test_concurrent_writes_one_wins(self, service, blueprint_id, bp_repo):
        """
        Simulate two writers reading version=1 simultaneously.
        Writer A writes first; Writer B must get ConcurrentModificationError.
        """
        # Both read version=1 (simulated by direct store peek — we don't
        # bypass service, so we need a direct repo hack):
        doc_before = bp_repo.load(blueprint_id)
        assert doc_before.version == 1

        # Writer A updates successfully
        service.update_draft(blueprint_id, {"name": "Writer A"})
        assert bp_repo.load(blueprint_id).version == 2

        # Force bp_repo store back to version=1 to simulate second writer
        # reading stale data (mongomock doesn't support real concurrency, so
        # we directly manipulate):
        result = bp_repo.update_with_version(
            blueprint_id=blueprint_id,
            spec={"name": "Writer B stale"},
            rid_refs=[],
            expected_version=1,  # stale
        )
        assert result is None  # OCC conflict

        # Live doc remains Writer A's
        assert bp_repo.load(blueprint_id).spec_dict["name"] == "Writer A"


# ===========================================================================
# R06: list_versions pagination stability
# ===========================================================================


class TestListVersionsPaginationRegression:
    def test_all_pages_covered_without_duplication(self, service, identity):
        bid = service.create_draft(identity=identity, draft_dict={"name": "Start"})
        for i in range(1, 6):
            service.update_draft(bid, {"name": f"Edit {i}"})
        # 5 edits → 5 snapshots (versions 1-5)

        page_size = 2
        all_versions = []
        page = 1
        while True:
            result = service.list_versions(bid, page=page, page_size=page_size)
            all_versions.extend(result["items"])
            if page >= result["total_pages"]:
                break
            page += 1

        version_numbers = [item["version"] for item in all_versions]
        assert len(version_numbers) == result["total"]
        assert len(version_numbers) == len(set(version_numbers))  # no duplicates
        assert sorted(version_numbers, reverse=True) == version_numbers  # desc order
