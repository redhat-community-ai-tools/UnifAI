"""
Unit tests for BlueprintService version-history operations (GENIE-1336).

All MongoDB dependencies are replaced with lightweight fakes so these
tests run without a real database.
"""

from __future__ import annotations

import copy
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, call, patch

import pytest
from mas.blueprints.exceptions import (
    BlueprintNotFoundError,
    ConcurrentModificationError,
    DuplicateSnapshotError,
    VersionNotFoundError,
)
from mas.blueprints.models.blueprint import BlueprintDocument, Identity
from mas.blueprints.models.blueprint_version import BlueprintVersionDocument
from mas.blueprints.repository.repository import BlueprintRepository
from mas.blueprints.repository.version_repository import BlueprintVersionRepository
from mas.blueprints.service import BlueprintService

# ---------------------------------------------------------------------------
# In-memory fakes  (testability via Dependency Injection)
# ---------------------------------------------------------------------------


class FakeBlueprintRepository(BlueprintRepository):
    """In-memory implementation for unit testing."""

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def _raw(self, blueprint_id: str) -> Dict[str, Any]:
        if blueprint_id not in self._store:
            raise KeyError(blueprint_id)
        return self._store[blueprint_id]

    def add(self, blueprint_id: str, spec: dict, version: int = 1) -> None:
        """Seed a document directly (test helper)."""
        self._store[blueprint_id] = {
            "blueprint_id": blueprint_id,
            "identity": {"type": "user", "id": "alice"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "spec_dict": copy.deepcopy(spec),
            "rid_refs": [],
            "metadata": {},
            "version": version,
        }

    # --- Repo interface ---

    def save(self, identity, spec, rid_refs, metadata=None) -> str:
        import uuid

        bid = uuid.uuid4().hex
        self._store[bid] = {
            "blueprint_id": bid,
            "identity": identity.model_dump(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "spec_dict": copy.deepcopy(spec),
            "rid_refs": rid_refs,
            "metadata": metadata or {},
            "version": 1,
        }
        return bid

    def update(self, blueprint_id, spec, rid_refs) -> bool:
        if blueprint_id not in self._store:
            return False
        self._store[blueprint_id]["spec_dict"] = copy.deepcopy(spec)
        self._store[blueprint_id]["rid_refs"] = rid_refs
        return True

    def update_with_version(self, blueprint_id, spec, rid_refs, expected_version) -> Optional[int]:
        raw = self._store.get(blueprint_id)
        if raw is None:
            return None
        stored_version = raw.get("version")  # may be absent (pre-migration doc)
        # Mirror the real repository behaviour: expected_version=1 accepts both
        # an explicit version=1 and a missing version field (pre-migration docs).
        if expected_version == 1:
            if stored_version is not None and stored_version != 1:
                return None  # OCC conflict — another writer bumped past 1
        else:
            if stored_version != expected_version:
                return None  # OCC conflict
        raw["spec_dict"] = copy.deepcopy(spec)
        raw["rid_refs"] = rid_refs
        raw["version"] = (stored_version or 1) + 1
        return raw["version"]

    def set_metadata(self, blueprint_id, metadata) -> bool:
        if blueprint_id not in self._store:
            return False
        self._store[blueprint_id]["metadata"] = metadata
        return True

    def delete(self, blueprint_id) -> bool:
        return self._store.pop(blueprint_id, None) is not None

    def delete_by_identity(self, identity) -> int:
        before = len(self._store)
        self._store = {
            k: v
            for k, v in self._store.items()
            if not (v["identity"]["type"] == identity.type and v["identity"]["id"] == identity.id)
        }
        return before - len(self._store)

    def load(self, blueprint_id) -> BlueprintDocument:
        raw = self._raw(blueprint_id)
        return BlueprintDocument.model_validate(raw)

    def load_many(self, blueprint_ids) -> List[BlueprintDocument]:
        return [self.load(bid) for bid in blueprint_ids if bid in self._store]

    def exists(self, blueprint_id) -> bool:
        return blueprint_id in self._store

    def list_ids(self, identity=None, skip=0, limit=20, sort_desc=True) -> List[str]:
        return list(self._store.keys())[skip : skip + limit]

    def list_docs(self, identity=None, skip=0, limit=20, sort_desc=True) -> List[BlueprintDocument]:
        docs = [self.load(bid) for bid in self._store]
        return docs[skip : skip + limit]

    def list_summaries(self, identity=None, skip=0, limit=20, sort_desc=True):
        return []

    def count(self, identity=None) -> int:
        return len(self._store)

    def list_direct_usage(self, rid) -> List[str]:
        return []

    def count_usage(self, rid) -> int:
        return 0


class FakeBlueprintVersionRepository(BlueprintVersionRepository):
    """In-memory implementation for unit testing."""

    def __init__(self):
        self._store: List[BlueprintVersionDocument] = []

    def insert_snapshot(self, version_doc: BlueprintVersionDocument) -> str:
        # Check uniqueness
        for existing in self._store:
            if (
                existing.blueprint_id == version_doc.blueprint_id
                and existing.version == version_doc.version
            ):
                raise DuplicateSnapshotError(
                    blueprint_id=version_doc.blueprint_id,
                    version=version_doc.version,
                )
        self._store.append(version_doc)
        return f"fake-id-{len(self._store)}"

    def find_by_blueprint_id(
        self, blueprint_id: str, page: int = 1, page_size: int = 20
    ) -> Tuple[List[BlueprintVersionDocument], int]:
        matching = [v for v in self._store if v.blueprint_id == blueprint_id]
        matching.sort(key=lambda v: v.version, reverse=True)
        total = len(matching)
        skip = (page - 1) * page_size
        items = matching[skip : skip + page_size]
        return items, total

    def find_one(self, blueprint_id: str, version: int) -> Optional[BlueprintVersionDocument]:
        for v in self._store:
            if v.blueprint_id == blueprint_id and v.version == version:
                return v
        return None

    def ensure_indexes(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SPEC_V1 = {"name": "Blueprint V1", "plan": [], "nodes": []}
SPEC_V2 = {"name": "Blueprint V2", "plan": [{"uid": "s1"}], "nodes": []}


@pytest.fixture()
def repo() -> FakeBlueprintRepository:
    r = FakeBlueprintRepository()
    r.add("bp-001", SPEC_V1, version=1)
    return r


@pytest.fixture()
def version_repo() -> FakeBlueprintVersionRepository:
    return FakeBlueprintVersionRepository()


@pytest.fixture()
def service(repo, version_repo) -> BlueprintService:
    return BlueprintService(repo=repo, version_repo=version_repo)


@pytest.fixture()
def service_no_version_repo(repo) -> BlueprintService:
    """Service without version repo — exercises legacy code path."""
    return BlueprintService(repo=repo)


# ===========================================================================
# Tests: update_draft (OCC + snapshot path)
# ===========================================================================


class TestUpdateDraftWithVersionRepo:
    def test_successful_update_increments_version(self, service, repo):
        service.update_draft("bp-001", SPEC_V2, user_id="user:alice")
        doc = repo.load("bp-001")
        assert doc.version == 2
        assert doc.spec_dict == SPEC_V2

    def test_snapshot_created_before_update(self, service, version_repo):
        service.update_draft("bp-001", SPEC_V2)
        items, total = version_repo.find_by_blueprint_id("bp-001")
        assert total == 1
        assert items[0].version == 1
        assert items[0].spec_dict_snapshot == SPEC_V1

    def test_snapshot_records_user_id(self, service, version_repo):
        service.update_draft("bp-001", SPEC_V2, user_id="user:bob")
        items, _ = version_repo.find_by_blueprint_id("bp-001")
        assert items[0].created_by == "user:bob"

    def test_snapshot_records_change_summary(self, service, version_repo):
        service.update_draft("bp-001", SPEC_V2, change_summary="Added LLM")
        items, _ = version_repo.find_by_blueprint_id("bp-001")
        assert items[0].change_summary == "Added LLM"

    def test_raises_blueprint_not_found(self, service):
        with pytest.raises(BlueprintNotFoundError):
            service.update_draft("nonexistent", SPEC_V2)

    def test_raises_concurrent_modification_on_occ_failure(self, service, repo):
        """
        OCC guard: update_with_version returns None when a concurrent writer
        has already bumped the version — service must raise
        ConcurrentModificationError.

        NOTE: the original test here set repo version=99 and relied on the
        since-removed consistency guard to trigger the error.  This version
        patches update_with_version directly so we exercise the real OCC path.
        """
        original_update_with_version = repo.update_with_version
        repo.update_with_version = lambda *args, **kwargs: None  # always report conflict

        try:
            with pytest.raises(ConcurrentModificationError) as exc_info:
                service.update_draft("bp-001", SPEC_V2)
            assert exc_info.value.blueprint_id == "bp-001"
        finally:
            repo.update_with_version = original_update_with_version  # restore

    def test_update_succeeds_when_prior_snapshot_is_missing(self, service, repo, version_repo):
        """
        Regression (GENIE-1336 fix): a blueprint at version > 1 that has no
        snapshot at (version - 1) must still be editable.

        Before the fix an overly-strict consistency guard would raise
        ConcurrentModificationError here, permanently blocking edits for any
        blueprint whose version history had a gap.
        """
        # Advance blueprint to version 5 with NO corresponding snapshots.
        repo._store["bp-001"]["version"] = 5
        # version_repo is empty — intentionally no snapshots seeded.

        result = service.update_draft("bp-001", SPEC_V2)
        assert result is True
        assert repo.load("bp-001").version == 6
        # A snapshot at version 5 should now exist (taken before the write).
        assert version_repo.find_one("bp-001", 5) is not None

    def test_multiple_sequential_updates_build_history(self, service, version_repo):
        spec_v2 = {"name": "V2"}
        spec_v3 = {"name": "V3"}
        service.update_draft("bp-001", spec_v2, change_summary="to V2")
        service.update_draft("bp-001", spec_v3, change_summary="to V3")
        _, total = version_repo.find_by_blueprint_id("bp-001")
        assert total == 2  # snapshots at v1 and v2


class TestUpdateDraftWithoutVersionRepo:
    """update_draft now requires version_repo — calls without it must fail."""

    def test_raises_runtime_error_without_version_repo(self, service_no_version_repo):
        with pytest.raises(RuntimeError, match="BlueprintVersionRepository"):
            service_no_version_repo.update_draft("bp-001", SPEC_V2)


# ===========================================================================
# Tests: list_versions
# ===========================================================================


class TestListVersions:
    def test_returns_empty_list_for_new_blueprint(self, service):
        result = service.list_versions("bp-001")
        assert result["total"] == 0
        assert result["items"] == []

    def test_raises_blueprint_not_found(self, service):
        with pytest.raises(BlueprintNotFoundError):
            service.list_versions("nonexistent")

    def test_returns_versions_sorted_newest_first(self, service, version_repo):
        # Manually seed versions in version_repo
        for v in [1, 2, 3]:
            version_repo._store.append(
                BlueprintVersionDocument(
                    blueprint_id="bp-001",
                    version=v,
                    spec_dict_snapshot={"version": v},
                )
            )
        result = service.list_versions("bp-001", page=1, page_size=10)
        versions = [item["version"] for item in result["items"]]
        assert versions == [3, 2, 1]

    def test_pagination_metadata(self, service, version_repo):
        for v in range(1, 6):
            version_repo._store.append(
                BlueprintVersionDocument(
                    blueprint_id="bp-001",
                    version=v,
                    spec_dict_snapshot={},
                )
            )
        result = service.list_versions("bp-001", page=1, page_size=2)
        assert result["total"] == 5
        assert result["page"] == 1
        assert result["page_size"] == 2
        assert result["total_pages"] == 3

    def test_raises_without_version_repo(self, service_no_version_repo):
        with pytest.raises(RuntimeError, match="BlueprintVersionRepository"):
            service_no_version_repo.list_versions("bp-001")

    def test_page_clamped_to_minimum_1(self, service):
        result = service.list_versions("bp-001", page=0)
        assert result["page"] == 1

    def test_page_size_clamped_to_max_100(self, service):
        result = service.list_versions("bp-001", page_size=999)
        assert result["page_size"] == 100


# ===========================================================================
# Tests: load_version
# ===========================================================================


class TestLoadVersion:
    def test_returns_detail_with_snapshot(self, service, version_repo):
        version_repo._store.append(
            BlueprintVersionDocument(
                blueprint_id="bp-001",
                version=1,
                spec_dict_snapshot=SPEC_V1,
                change_summary="Initial",
            )
        )
        detail = service.load_version("bp-001", 1)
        assert detail["version"] == 1
        assert detail["spec_dict_snapshot"] == SPEC_V1

    def test_raises_version_not_found(self, service):
        with pytest.raises(VersionNotFoundError) as exc_info:
            service.load_version("bp-001", 999)
        assert exc_info.value.blueprint_id == "bp-001"
        assert exc_info.value.version == 999

    def test_raises_blueprint_not_found(self, service):
        with pytest.raises(BlueprintNotFoundError):
            service.load_version("nonexistent", 1)

    def test_raises_without_version_repo(self, service_no_version_repo):
        with pytest.raises(RuntimeError):
            service_no_version_repo.load_version("bp-001", 1)


# ===========================================================================
# Tests: restore_version
# ===========================================================================


class TestRestoreVersion:
    def test_successful_restore_sets_new_live_spec(self, service, repo, version_repo):
        # Seed a version 1 snapshot
        version_repo._store.append(
            BlueprintVersionDocument(
                blueprint_id="bp-001",
                version=1,
                spec_dict_snapshot={"name": "OldSpec"},
            )
        )
        # Set repo to version 2
        repo._store["bp-001"]["spec_dict"] = {"name": "NewerSpec"}
        repo._store["bp-001"]["version"] = 2

        service.restore_version("bp-001", target_version=1)
        doc = repo.load("bp-001")
        assert doc.spec_dict == {"name": "OldSpec"}
        assert doc.version == 3  # was 2 → snapshot at 2 → OCC bumps to 3

    def test_restore_creates_snapshot_of_current_state_first(self, service, repo, version_repo):
        version_repo._store.append(
            BlueprintVersionDocument(
                blueprint_id="bp-001",
                version=1,
                spec_dict_snapshot=SPEC_V1,
            )
        )
        repo._store["bp-001"]["version"] = 2
        repo._store["bp-001"]["spec_dict"] = SPEC_V2

        service.restore_version("bp-001", target_version=1, user_id="user:alice")

        # There should now be snapshots for version 1 (pre-seeded) and version 2 (pre-restore)
        _, total = version_repo.find_by_blueprint_id("bp-001")
        assert total == 2

    def test_restore_change_summary_references_target_version(self, service, repo, version_repo):
        version_repo._store.append(
            BlueprintVersionDocument(
                blueprint_id="bp-001",
                version=1,
                spec_dict_snapshot=SPEC_V1,
            )
        )
        repo._store["bp-001"]["version"] = 2
        repo._store["bp-001"]["spec_dict"] = SPEC_V2

        service.restore_version("bp-001", target_version=1)
        items, _ = version_repo.find_by_blueprint_id("bp-001")
        # The newest snapshot should say "Restored to version 1"
        assert any("Restored to version 1" in (item.change_summary or "") for item in items)

    def test_raises_version_not_found(self, service):
        with pytest.raises(VersionNotFoundError):
            service.restore_version("bp-001", target_version=999)

    def test_raises_blueprint_not_found(self, service):
        with pytest.raises(BlueprintNotFoundError):
            service.restore_version("nonexistent", target_version=1)

    def test_raises_without_version_repo(self, service_no_version_repo):
        with pytest.raises(RuntimeError):
            service_no_version_repo.restore_version("bp-001", target_version=1)


# ===========================================================================
# Tests: _extract_rid_refs
# ===========================================================================


class TestExtractRidRefs:
    def test_no_refs_returns_empty(self, service):
        assert service._extract_rid_refs({"name": "Test"}) == []

    def test_single_ref_extracted(self, service):
        refs = service._extract_rid_refs({"config": {"$ref": "resource:123"}})
        assert refs == ["resource:123"]

    def test_nested_refs_extracted(self, service):
        draft = {
            "nodes": [
                {"config": {"$ref": "r1"}},
                {"config": {"$ref": "r2"}},
            ]
        }
        refs = service._extract_rid_refs(draft)
        assert set(refs) == {"r1", "r2"}

    def test_deduplication(self, service):
        draft = {
            "a": {"$ref": "same-ref"},
            "b": {"$ref": "same-ref"},
        }
        refs = service._extract_rid_refs(draft)
        assert refs.count("same-ref") == 1
