"""
Integration tests — Workflow Editing Scenarios (GENIE-1336).

Authored by the QE Deep Agent; saved and verified by the SDE Agent.

These tests cover the full vertical slice:
    BlueprintService → MongoBlueprintRepository / MongoBlueprintVersionRepository
    → mongomock in-process database

They do NOT test the HTTP layer (that is covered in
``test_blueprint_version_endpoints.py``).  Instead they validate the exact
business rules the API layer delegates to: version increments, snapshot
fidelity, OCC semantics, history-gap tolerance, legacy-document support,
version-list pagination, and restore correctness.

Scenario catalogue
------------------
WE-01  Create a new blueprint workflow
WE-02  Edit a blueprint — spec is updated live
WE-03  Edit a blueprint — pre-edit snapshot is created
WE-04  Multiple sequential edits — versions increment monotonically
WE-05  Change summary is persisted and retrievable
WE-06  Concurrent modification — OCC rejects the stale writer
WE-07  Edit with history gap — must succeed (regression for GENIE-1336 guard bug)
WE-08  Edit pre-migration blueprint — no version field → edit writes version=2
WE-09  Multiple edits after first edit on pre-migration blueprint
WE-10  List version history — returns versions newest-first
WE-11  Version history pagination — no duplicates, full coverage
WE-12  Load specific version detail — spec_dict_snapshot matches original
WE-13  Load non-existent version raises VersionNotFoundError
WE-14  Load version on non-existent blueprint raises BlueprintNotFoundError
WE-15  Restore rolls back live spec to target snapshot
WE-16  Restore preserves pre-restore state as a new snapshot
WE-17  Restore is itself reversible (re-restore goes forward again)
WE-18  Restore on missing blueprint raises BlueprintNotFoundError
WE-19  Restore on missing version snapshot raises VersionNotFoundError
WE-20  list_versions raises RuntimeError when version_repo is not configured
WE-21  update_draft uses legacy unconditional path when version_repo is None
WE-22  $ref extraction — rid_refs are deduplicated across nested structures
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import pytest

try:
    import mongomock
    _MONGOMOCK_AVAILABLE = True
except ImportError:
    _MONGOMOCK_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _MONGOMOCK_AVAILABLE, reason="mongomock is not installed"
)

from adapters.outbound.mongo.blueprint_repository import MongoBlueprintRepository
from adapters.outbound.mongo.blueprint_version_repository import (
    MongoBlueprintVersionRepository,
)
from lib.mas.blueprints.exceptions import (
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
    """Fresh mongomock client per test — complete isolation."""
    return mongomock.MongoClient()


@pytest.fixture()
def bp_col(mongo_client):
    return mongo_client["genie"]["blueprints"]


@pytest.fixture()
def ver_col(mongo_client):
    return mongo_client["genie"]["blueprint_versions"]


@pytest.fixture()
def bp_repo(bp_col):
    return MongoBlueprintRepository(col=bp_col)


@pytest.fixture()
def ver_repo(ver_col):
    repo = MongoBlueprintVersionRepository(col=ver_col)
    repo.ensure_indexes()
    return repo


@pytest.fixture()
def service(bp_repo, ver_repo):
    """Full service with both repositories wired (versioning enabled)."""
    return BlueprintService(repo=bp_repo, version_repo=ver_repo)


@pytest.fixture()
def legacy_service(bp_repo):
    """Service without version_repo — legacy unconditional-update path."""
    return BlueprintService(repo=bp_repo)


@pytest.fixture()
def alice() -> Identity:
    return Identity(type="user", id="u-alice")


@pytest.fixture()
def bob() -> Identity:
    return Identity(type="user", id="u-bob")


def _make_spec(name: str = "My Workflow", **extra: Any) -> Dict[str, Any]:
    """Return a minimal blueprint spec dict."""
    return {"name": name, "plan": [], **extra}


def _insert_legacy_doc(bp_col, identity: Identity, spec: Dict[str, Any]) -> str:
    """
    Insert a blueprint that has no ``version`` field, simulating a document
    created before the GENIE-1336 migration.
    """
    bid = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    bp_col.insert_one(
        {
            "blueprint_id": bid,
            "identity": identity.model_dump(),
            "spec_dict": spec,
            "rid_refs": [],
            "metadata": {},
            "created_at": now,
            "updated_at": now,
            # Deliberately NO 'version' field.
        }
    )
    return bid


# ===========================================================================
# WE-01  Create a new blueprint workflow
# ===========================================================================


class TestWorkflowCreate:
    """WE-01: A new blueprint is persisted with version=1 and correct spec."""

    def test_create_returns_non_empty_id(self, service, alice):
        bid = service.create_draft(
            identity=alice, draft_dict=_make_spec("First Workflow")
        )
        assert isinstance(bid, str) and len(bid) > 0

    def test_created_document_has_version_1(self, service, alice, bp_repo):
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        doc = bp_repo.load(bid)
        assert doc.version == 1

    def test_created_document_stores_spec(self, service, alice, bp_repo):
        spec = _make_spec("WE-01 Workflow", description="desc", plan=[{"uid": "s1"}])
        bid = service.create_draft(identity=alice, draft_dict=spec)
        doc = bp_repo.load(bid)
        assert doc.spec_dict == spec

    def test_created_document_stores_identity(self, service, alice, bp_repo):
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        doc = bp_repo.load(bid)
        assert doc.identity == alice

    def test_create_does_not_produce_initial_snapshot(self, service, alice, ver_repo):
        """No snapshot should exist immediately after creation (only on first edit)."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        _, total = ver_repo.find_by_blueprint_id(bid)
        assert total == 0


# ===========================================================================
# WE-02 / WE-03  Edit a blueprint — live spec update + pre-edit snapshot
# ===========================================================================


class TestWorkflowEditBasic:
    """WE-02 & WE-03: update_draft updates the live spec and records a snapshot."""

    def test_edit_updates_live_spec(self, service, alice, bp_repo):
        """WE-02: live spec is replaced by the new draft."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("Before"))
        service.update_draft(bid, _make_spec("After"))
        doc = bp_repo.load(bid)
        assert doc.spec_dict["name"] == "After"

    def test_edit_increments_version(self, service, alice, bp_repo):
        """WE-02: version field goes from 1 → 2 after the first edit."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        service.update_draft(bid, _make_spec("V2"))
        doc = bp_repo.load(bid)
        assert doc.version == 2

    def test_edit_creates_pre_edit_snapshot(self, service, alice, ver_repo):
        """WE-03: A snapshot of the ORIGINAL spec is created before overwriting."""
        original_spec = _make_spec("Original")
        bid = service.create_draft(identity=alice, draft_dict=original_spec)
        service.update_draft(bid, _make_spec("Updated"))

        items, total = ver_repo.find_by_blueprint_id(bid)
        assert total == 1
        snapshot = ver_repo.find_one(bid, 1)
        assert snapshot is not None
        assert snapshot.spec_dict_snapshot == original_spec

    def test_snapshot_is_independent_of_live_doc(self, service, alice, bp_repo, ver_repo):
        """WE-03: Mutating live doc later does not affect the stored snapshot."""
        original_spec = _make_spec("Snap Check")
        bid = service.create_draft(identity=alice, draft_dict=original_spec)
        service.update_draft(bid, _make_spec("Changed"))

        # Confirm live doc changed
        live = bp_repo.load(bid)
        assert live.spec_dict["name"] == "Changed"

        # Snapshot must still hold original
        snap = ver_repo.find_one(bid, 1)
        assert snap is not None
        assert snap.spec_dict_snapshot["name"] == "Snap Check"

    def test_edit_returns_true_on_success(self, service, alice):
        """update_draft returns True on success."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        result = service.update_draft(bid, _make_spec("Updated"))
        assert result is True

    def test_edit_on_missing_blueprint_raises(self, service):
        """Editing a nonexistent blueprint raises BlueprintNotFoundError."""
        with pytest.raises(BlueprintNotFoundError):
            service.update_draft("does-not-exist", _make_spec("Ghost"))


# ===========================================================================
# WE-04  Multiple sequential edits
# ===========================================================================


class TestWorkflowEditSequential:
    """WE-04: Version increments are monotonic and all snapshots are created."""

    def test_version_increments_sequentially(self, service, alice, bp_repo):
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        for expected in [2, 3, 4, 5]:
            service.update_draft(bid, _make_spec(f"V{expected}"))
            doc = bp_repo.load(bid)
            assert doc.version == expected

    def test_snapshot_count_matches_edit_count(self, service, alice, ver_repo):
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("Start"))
        edits = 5
        for i in range(edits):
            service.update_draft(bid, _make_spec(f"Edit {i + 1}"))
        _, total = ver_repo.find_by_blueprint_id(bid)
        assert total == edits  # one snapshot per edit (pre-update state)

    def test_each_snapshot_holds_correct_spec(self, service, alice, ver_repo):
        """Each snapshot captures the spec that was live BEFORE that edit."""
        names = ["Alpha", "Beta", "Gamma", "Delta"]
        bid = service.create_draft(identity=alice, draft_dict=_make_spec(names[0]))
        for i in range(1, len(names)):
            service.update_draft(bid, _make_spec(names[i]))

        for version, expected_name in enumerate(names[:-1], start=1):
            snap = ver_repo.find_one(bid, version)
            assert snap is not None, f"Snapshot v{version} is missing"
            assert snap.spec_dict_snapshot["name"] == expected_name

    def test_live_spec_after_multiple_edits(self, service, alice, bp_repo):
        """Live doc always reflects the last edit."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        for i in range(2, 6):
            service.update_draft(bid, _make_spec(f"V{i}"))
        doc = bp_repo.load(bid)
        assert doc.spec_dict["name"] == "V5"


# ===========================================================================
# WE-05  Change summary is persisted and retrievable
# ===========================================================================


class TestWorkflowEditChangeSummary:
    """WE-05: change_summary is stored in the snapshot and exposed via load_version."""

    def test_change_summary_is_persisted(self, service, alice, ver_repo):
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("Orig"))
        service.update_draft(bid, _make_spec("Updated"), change_summary="Added step A")

        snap = ver_repo.find_one(bid, 1)
        assert snap is not None
        assert snap.change_summary == "Added step A"

    def test_change_summary_surfaced_in_load_version(self, service, alice):
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("Orig"))
        service.update_draft(bid, _make_spec("V2"), change_summary="Big refactor")

        detail = service.load_version(bid, 1)
        assert detail["change_summary"] == "Big refactor"

    def test_none_change_summary_is_stored_as_none(self, service, alice, ver_repo):
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        service.update_draft(bid, _make_spec("V2"))  # no change_summary

        snap = ver_repo.find_one(bid, 1)
        assert snap is not None
        assert snap.change_summary is None

    def test_user_id_is_stored_in_snapshot(self, service, alice, ver_repo):
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        service.update_draft(bid, _make_spec("V2"), user_id="u:alice")

        snap = ver_repo.find_one(bid, 1)
        assert snap is not None
        assert snap.created_by == "u:alice"

    def test_change_summary_max_length_accepted(self, service, alice, ver_repo):
        """500-character change_summary is the upper limit — must be accepted."""
        long_summary = "x" * 500
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        service.update_draft(bid, _make_spec("V2"), change_summary=long_summary)
        snap = ver_repo.find_one(bid, 1)
        assert snap is not None
        assert snap.change_summary == long_summary


# ===========================================================================
# WE-06  OCC — concurrent modification is rejected
# ===========================================================================


class TestWorkflowEditOCC:
    """WE-06: Optimistic Concurrency Control prevents lost updates."""

    def test_concurrent_write_on_stale_version_returns_none(self, bp_repo, ver_repo):
        """
        Direct repo-level test: update_with_version with wrong expected_version
        returns None (the OCC guard is working).
        """
        svc = BlueprintService(repo=bp_repo, version_repo=ver_repo)
        identity = Identity(type="user", id="u-occ")
        bid = svc.create_draft(identity=identity, draft_dict=_make_spec("V1"))

        # Simulate writer A advancing the version
        svc.update_draft(bid, _make_spec("Writer A"))

        # Writer B tries with the stale expected_version=1
        result = bp_repo.update_with_version(
            blueprint_id=bid,
            spec=_make_spec("Writer B stale"),
            rid_refs=[],
            expected_version=1,  # stale — version is now 2
        )
        assert result is None

    def test_live_doc_unchanged_after_rejected_write(self, service, alice, bp_repo):
        """After OCC rejection the live document still holds Writer A's data."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        service.update_draft(bid, _make_spec("Writer A"))

        # Direct OCC-rejected write
        bp_repo.update_with_version(
            blueprint_id=bid,
            spec=_make_spec("Writer B stale"),
            rid_refs=[],
            expected_version=1,
        )

        doc = bp_repo.load(bid)
        assert doc.spec_dict["name"] == "Writer A"

    def test_service_raises_concurrent_modification_error(self, service, alice, monkeypatch):
        """
        ConcurrentModificationError is raised when ``update_with_version``
        returns ``None`` — the signal that the OCC guard rejected the write
        because another writer advanced the version between our read and write.

        We cannot emulate true parallelism with mongomock, so we simulate the
        race by patching ``update_with_version`` to unconditionally return
        ``None`` (as it does on a real OCC conflict).  This tests the service
        layer's response without depending on DB internals.
        """
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))

        # Patch the OCC write to simulate a concurrent modification conflict.
        monkeypatch.setattr(
            service._repo,
            "update_with_version",
            lambda blueprint_id, spec, rid_refs, expected_version: None,
        )

        with pytest.raises(ConcurrentModificationError):
            service.update_draft(bid, _make_spec("Conflicted"))

    def test_occ_guard_does_not_block_sequential_writes(self, service, alice, bp_repo):
        """
        Sequential writes (read-edit-write loop) must all succeed —
        OCC only blocks *concurrent* stale writers.
        """
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        for i in range(2, 8):
            result = service.update_draft(bid, _make_spec(f"V{i}"))
            assert result is True
        doc = bp_repo.load(bid)
        assert doc.version == 7


# ===========================================================================
# WE-07  Edit with history gap (regression guard for GENIE-1336 bug)
# ===========================================================================


class TestWorkflowEditHistoryGap:
    """
    WE-07: Editing a blueprint whose snapshot history has gaps must succeed.

    Before the GENIE-1336 fix a "consistency guard" checked that a snapshot
    existed at (current_version - 1) and raised an error if it was missing.
    That guard was removed; the fix is exercised by deleting all snapshots and
    confirming that subsequent edits still work.
    """

    def test_edit_succeeds_when_all_snapshots_are_missing(
        self, service, alice, bp_col, ver_repo
    ):
        """WE-07a: History completely absent — edit must still succeed."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        service.update_draft(bid, _make_spec("V2"))
        # Blueprint is now version=2; delete ALL snapshots to create a gap.
        ver_repo._col.delete_many({"blueprint_id": bid})

        result = service.update_draft(bid, _make_spec("V3 after gap"))
        assert result is True

    def test_version_is_incremented_after_gap_edit(
        self, service, alice, bp_col, ver_repo
    ):
        """WE-07b: Version continues incrementing past the gap."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        service.update_draft(bid, _make_spec("V2"))
        ver_repo._col.delete_many({"blueprint_id": bid})

        service.update_draft(bid, _make_spec("V3 after gap"))

        raw = bp_col.find_one({"blueprint_id": bid})
        assert raw["version"] == 3

    def test_new_snapshot_recorded_for_pre_gap_state(
        self, service, alice, ver_repo
    ):
        """
        WE-07c: Even after a history gap, the pre-edit state is snapshotted
        so future restores have a reference point.
        """
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        service.update_draft(bid, _make_spec("V2"))
        ver_repo._col.delete_many({"blueprint_id": bid})

        service.update_draft(bid, _make_spec("V3 after gap"))

        snap = ver_repo.find_one(bid, 2)
        assert snap is not None
        assert snap.spec_dict_snapshot["name"] == "V2"

    def test_further_edits_work_after_gap_recovery(
        self, service, alice, ver_repo
    ):
        """WE-07d: Further sequential edits work normally after the gap-edit."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        service.update_draft(bid, _make_spec("V2"))
        ver_repo._col.delete_many({"blueprint_id": bid})
        service.update_draft(bid, _make_spec("V3"))
        service.update_draft(bid, _make_spec("V4"))
        service.update_draft(bid, _make_spec("V5"))
        _, total = ver_repo.find_by_blueprint_id(bid)
        assert total == 3  # snapshots at v2, v3, v4


# ===========================================================================
# WE-08 / WE-09  Pre-migration blueprint (no version field)
# ===========================================================================


class TestWorkflowEditLegacy:
    """
    WE-08 & WE-09: Blueprints created before the GENIE-1336 migration have no
    ``version`` field.  The first edit must succeed and write version=2; every
    subsequent edit uses the normal OCC path.
    """

    def test_first_edit_on_legacy_doc_succeeds(self, service, alice, bp_col, ver_repo):
        """WE-08: First edit on a pre-migration (no-version-field) document."""
        spec = _make_spec("Legacy Blueprint")
        bid = _insert_legacy_doc(bp_col, alice, spec)

        result = service.update_draft(bid, _make_spec("First Edit"))
        assert result is True

    def test_first_edit_writes_version_2(self, service, alice, bp_col):
        """WE-08: After the first edit the document has version=2."""
        bid = _insert_legacy_doc(bp_col, alice, _make_spec("Legacy"))
        service.update_draft(bid, _make_spec("Edited"))

        raw = bp_col.find_one({"blueprint_id": bid})
        assert raw["version"] == 2

    def test_first_edit_creates_snapshot_at_version_1(
        self, service, alice, bp_col, ver_repo
    ):
        """WE-08: A snapshot of the legacy spec is created at version=1."""
        original_spec = _make_spec("Legacy Content")
        bid = _insert_legacy_doc(bp_col, alice, original_spec)
        service.update_draft(bid, _make_spec("Updated"))

        snap = ver_repo.find_one(bid, 1)
        assert snap is not None
        assert snap.spec_dict_snapshot == original_spec

    def test_multiple_edits_after_legacy_first_edit(
        self, service, alice, bp_col, ver_repo
    ):
        """WE-09: Subsequent edits after the first on a legacy doc work correctly."""
        bid = _insert_legacy_doc(bp_col, alice, _make_spec("Legacy V1"))
        service.update_draft(bid, _make_spec("Edit 1"))
        service.update_draft(bid, _make_spec("Edit 2"))
        service.update_draft(bid, _make_spec("Edit 3"))

        raw = bp_col.find_one({"blueprint_id": bid})
        assert raw["version"] == 4  # 1 (implicit) → 2 → 3 → 4

        _, total = ver_repo.find_by_blueprint_id(bid)
        assert total == 3  # snapshots at v1, v2, v3


# ===========================================================================
# WE-10 / WE-11  Version history listing and pagination
# ===========================================================================


class TestWorkflowVersionHistory:
    """WE-10 & WE-11: list_versions returns correct paginated results."""

    def test_list_returns_versions_newest_first(self, service, alice):
        """WE-10: Items are ordered descending by version number."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        for i in range(2, 6):
            service.update_draft(bid, _make_spec(f"V{i}"))

        result = service.list_versions(bid)
        versions = [item["version"] for item in result["items"]]
        assert versions == sorted(versions, reverse=True)

    def test_list_total_matches_edit_count(self, service, alice):
        """WE-10: total reflects exactly how many edits were made."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        edits = 6
        for i in range(edits):
            service.update_draft(bid, _make_spec(f"Edit {i}"))

        result = service.list_versions(bid)
        assert result["total"] == edits

    def test_list_summary_excludes_spec_dict_snapshot(self, service, alice):
        """WE-10: list items must NOT include the heavyweight spec_dict_snapshot."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        service.update_draft(bid, _make_spec("V2"))

        result = service.list_versions(bid)
        for item in result["items"]:
            assert "spec_dict_snapshot" not in item

    def test_list_on_missing_blueprint_raises(self, service):
        """WE-10: BlueprintNotFoundError for unknown blueprint_id."""
        with pytest.raises(BlueprintNotFoundError):
            service.list_versions("ghost-id")

    def test_list_empty_for_blueprint_with_no_edits(self, service, alice):
        """WE-10: Fresh blueprint has no snapshots yet."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        result = service.list_versions(bid)
        assert result["total"] == 0
        assert result["items"] == []

    def test_pagination_covers_all_versions_without_duplicates(self, service, alice):
        """WE-11: Crawling all pages produces exactly the right set of versions."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("Start"))
        for i in range(1, 8):
            service.update_draft(bid, _make_spec(f"Edit {i}"))
        # 7 edits → 7 snapshots

        page_size = 3
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
        assert len(version_numbers) == len(set(version_numbers)), "Duplicate versions found"
        assert sorted(version_numbers, reverse=True) == version_numbers

    def test_pagination_metadata_is_accurate(self, service, alice):
        """WE-11: page, page_size, total_pages fields are correct."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        for i in range(5):
            service.update_draft(bid, _make_spec(f"E{i}"))

        result = service.list_versions(bid, page=1, page_size=2)
        assert result["page"] == 1
        assert result["page_size"] == 2
        assert result["total"] == 5
        assert result["total_pages"] == 3  # ceil(5/2)


# ===========================================================================
# WE-12 / WE-13 / WE-14  Load specific version detail
# ===========================================================================


class TestWorkflowVersionLoad:
    """WE-12–14: load_version returns the correct snapshot or raises errors."""

    def test_load_version_returns_correct_snapshot(self, service, alice):
        """WE-12: Snapshot at version N holds the spec that was live at version N."""
        specs = [_make_spec("V1"), _make_spec("V2"), _make_spec("V3")]
        bid = service.create_draft(identity=alice, draft_dict=specs[0])
        service.update_draft(bid, specs[1])
        service.update_draft(bid, specs[2])

        assert service.load_version(bid, 1)["spec_dict_snapshot"] == specs[0]
        assert service.load_version(bid, 2)["spec_dict_snapshot"] == specs[1]

    def test_load_version_includes_all_summary_fields(self, service, alice):
        """WE-12: Response has blueprint_id, version, created_by, created_at, change_summary."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        service.update_draft(
            bid, _make_spec("V2"), user_id="u:alice", change_summary="First change"
        )

        detail = service.load_version(bid, 1)
        assert detail["blueprint_id"] == bid
        assert detail["version"] == 1
        assert detail["created_by"] == "u:alice"
        assert "created_at" in detail
        assert detail["change_summary"] == "First change"
        assert "spec_dict_snapshot" in detail

    def test_load_version_raises_for_nonexistent_version(self, service, alice):
        """WE-13: VersionNotFoundError for a version number that has no snapshot."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        service.update_draft(bid, _make_spec("V2"))

        with pytest.raises(VersionNotFoundError):
            service.load_version(bid, 9999)

    def test_load_version_raises_for_nonexistent_blueprint(self, service):
        """WE-14: BlueprintNotFoundError when the blueprint itself is absent."""
        with pytest.raises(BlueprintNotFoundError):
            service.load_version("nonexistent-bp", 1)


# ===========================================================================
# WE-15 / WE-16 / WE-17 / WE-18 / WE-19  Restore operations
# ===========================================================================


class TestWorkflowRestore:
    """WE-15–19: restore_version correctness and error handling."""

    def test_restore_rolls_back_live_spec(self, service, alice, bp_repo):
        """WE-15: After restore, the live spec matches the target snapshot."""
        original_spec = _make_spec("Original Plan", plan=[{"uid": "s0"}])
        bid = service.create_draft(identity=alice, draft_dict=original_spec)
        service.update_draft(bid, _make_spec("Modified Plan", plan=[{"uid": "s1"}]))

        service.restore_version(bid, target_version=1, user_id="u:alice")

        doc = bp_repo.load(bid)
        assert doc.spec_dict == original_spec

    def test_restore_increments_version(self, service, alice, bp_repo):
        """WE-15: Restore is itself an edit — version increments."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        service.update_draft(bid, _make_spec("V2"))
        service.restore_version(bid, target_version=1)

        doc = bp_repo.load(bid)
        assert doc.version == 3

    def test_restore_preserves_pre_restore_state_as_snapshot(
        self, service, alice, ver_repo, bp_repo
    ):
        """
        WE-16: Before overwriting with the restore, the current (pre-restore)
        state is saved as a new snapshot so no history is lost.
        """
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        service.update_draft(bid, _make_spec("V2"))
        # At this point: snapshot at v1, live is v2
        service.restore_version(bid, target_version=1)
        # Should now have snapshots at v1 (from edit) and v2 (from restore)
        _, total = ver_repo.find_by_blueprint_id(bid)
        assert total == 2

    def test_restore_is_reversible(self, service, alice, bp_repo):
        """
        WE-17: A restore can itself be undone by restoring to the version
        that was active immediately before the restore.

        Timeline:
          create → V1 spec
          edit   → V2 spec (snapshot at v1)
          restore to v1 → live is V1 spec again (snapshot at v2)
          restore to v2 → live is V2 spec again
        """
        v1_spec = _make_spec("V1 Original")
        v2_spec = _make_spec("V2 Modified")
        bid = service.create_draft(identity=alice, draft_dict=v1_spec)
        service.update_draft(bid, v2_spec)  # live=V2, snap at v1
        service.restore_version(bid, target_version=1)  # live=V1, snap at v2
        service.restore_version(bid, target_version=2)  # live=V2, snap at v3

        doc = bp_repo.load(bid)
        assert doc.spec_dict == v2_spec

    def test_restore_change_summary_is_generated(self, service, alice, ver_repo):
        """WE-16: The auto-generated change_summary for a restore is 'Restored to version N'."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        service.update_draft(bid, _make_spec("V2"))
        service.restore_version(bid, target_version=1)

        # The snapshot taken before the restore was at v2.
        snap = ver_repo.find_one(bid, 2)
        assert snap is not None
        assert snap.change_summary == "Restored to version 1"

    def test_restore_returns_true_on_success(self, service, alice):
        """WE-15: restore_version returns True on success."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec("V1"))
        service.update_draft(bid, _make_spec("V2"))
        result = service.restore_version(bid, target_version=1)
        assert result is True

    def test_restore_on_missing_blueprint_raises(self, service):
        """WE-18: BlueprintNotFoundError when the blueprint doesn't exist."""
        with pytest.raises(BlueprintNotFoundError):
            service.restore_version("ghost-bp", target_version=1)

    def test_restore_on_missing_snapshot_raises(self, service, alice):
        """WE-19: VersionNotFoundError when the target version snapshot is absent."""
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        service.update_draft(bid, _make_spec("V2"))
        with pytest.raises(VersionNotFoundError):
            service.restore_version(bid, target_version=999)


# ===========================================================================
# WE-20  RuntimeError when version_repo is not configured
# ===========================================================================


class TestWorkflowVersioningUnconfigured:
    """WE-20: Service raises RuntimeError when version-history features are used
    without version_repo injected."""

    def test_list_versions_raises_runtime_error(self, legacy_service, alice, bp_repo):
        bid = bp_repo.save(identity=alice, spec=_make_spec(), rid_refs=[])
        with pytest.raises(RuntimeError, match="BlueprintVersionRepository"):
            legacy_service.list_versions(bid)

    def test_load_version_raises_runtime_error(self, legacy_service, alice, bp_repo):
        bid = bp_repo.save(identity=alice, spec=_make_spec(), rid_refs=[])
        with pytest.raises(RuntimeError, match="BlueprintVersionRepository"):
            legacy_service.load_version(bid, 1)

    def test_restore_version_raises_runtime_error(self, legacy_service, alice, bp_repo):
        bid = bp_repo.save(identity=alice, spec=_make_spec(), rid_refs=[])
        with pytest.raises(RuntimeError, match="BlueprintVersionRepository"):
            legacy_service.restore_version(bid, target_version=1)


# ===========================================================================
# WE-21  Legacy unconditional update path (version_repo=None)
# ===========================================================================


class TestWorkflowLegacyUpdatePath:
    """WE-21: When version_repo is None, update_draft uses the unconditional repo.update()
    path — no OCC, no snapshots."""

    def test_legacy_update_succeeds_without_version_repo(
        self, legacy_service, alice, bp_repo
    ):
        bid = bp_repo.save(identity=alice, spec=_make_spec("Legacy V1"), rid_refs=[])
        result = legacy_service.update_draft(bid, _make_spec("Legacy V2"))
        assert result is True

    def test_legacy_update_overwrites_spec(self, legacy_service, alice, bp_repo):
        bid = bp_repo.save(identity=alice, spec=_make_spec("Old"), rid_refs=[])
        legacy_service.update_draft(bid, _make_spec("New"))
        doc = bp_repo.load(bid)
        assert doc.spec_dict["name"] == "New"

    def test_legacy_update_does_not_increment_version(
        self, legacy_service, alice, bp_repo
    ):
        """Unconditional update never touches the version field."""
        bid = bp_repo.save(identity=alice, spec=_make_spec(), rid_refs=[])
        legacy_service.update_draft(bid, _make_spec("Updated"))
        doc = bp_repo.load(bid)
        assert doc.version == 1  # unchanged

    def test_legacy_update_on_missing_blueprint_raises(self, legacy_service):
        with pytest.raises(BlueprintNotFoundError):
            legacy_service.update_draft("ghost-id", _make_spec())


# ===========================================================================
# WE-22  $ref extraction and rid_refs deduplication
# ===========================================================================


class TestWorkflowRefExtraction:
    """WE-22: BlueprintService correctly extracts and deduplicates $ref values."""

    def test_top_level_ref_is_extracted(self, service, alice, bp_repo):
        spec = {"name": "W", "$ref": "rid://tool-a", "plan": []}
        bid = service.create_draft(identity=alice, draft_dict=spec)
        doc = bp_repo.load(bid)
        assert "rid://tool-a" in doc.rid_refs

    def test_nested_refs_are_extracted(self, service, alice, bp_repo):
        spec = {
            "name": "W",
            "plan": [
                {"uid": "s1", "$ref": "rid://tool-b"},
                {"uid": "s2", "config": {"$ref": "rid://tool-c"}},
            ],
        }
        bid = service.create_draft(identity=alice, draft_dict=spec)
        doc = bp_repo.load(bid)
        assert "rid://tool-b" in doc.rid_refs
        assert "rid://tool-c" in doc.rid_refs

    def test_duplicate_refs_are_deduplicated(self, service, alice, bp_repo):
        spec = {
            "name": "W",
            "plan": [
                {"uid": "s1", "$ref": "rid://shared-tool"},
                {"uid": "s2", "$ref": "rid://shared-tool"},
            ],
        }
        bid = service.create_draft(identity=alice, draft_dict=spec)
        doc = bp_repo.load(bid)
        assert doc.rid_refs.count("rid://shared-tool") == 1

    def test_spec_with_no_refs_produces_empty_rid_refs(self, service, alice, bp_repo):
        bid = service.create_draft(identity=alice, draft_dict=_make_spec())
        doc = bp_repo.load(bid)
        assert doc.rid_refs == []
