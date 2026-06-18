"""
Unit tests for BlueprintService edge cases and boundary conditions.

Exercises behaviours not covered by the primary service versioning tests:
  - page/page_size clamping
  - _require_version_repo guard
  - dual-path branching
  - snapshot idempotency on DuplicateKeyError
  - rid_refs extraction corner cases
  - restore_version change_summary format
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

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
# Minimal in-memory fakes (local to this file)
# ---------------------------------------------------------------------------


class _FakeBPRepo(BlueprintRepository):
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def _seed(self, blueprint_id: str, spec: dict, version: int = 1):
        self._store[blueprint_id] = {
            "blueprint_id": blueprint_id,
            "identity": {"type": "user", "id": "test"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "spec_dict": copy.deepcopy(spec),
            "rid_refs": [],
            "metadata": {},
            "version": version,
        }

    def save(self, identity, spec, rid_refs, metadata=None) -> str:
        import uuid

        bid = uuid.uuid4().hex
        self._seed(bid, spec)
        return bid

    def update(self, blueprint_id, spec, rid_refs) -> bool:
        if blueprint_id not in self._store:
            return False
        self._store[blueprint_id]["spec_dict"] = copy.deepcopy(spec)
        return True

    def update_with_version(self, blueprint_id, spec, rid_refs, expected_version) -> Optional[int]:
        raw = self._store.get(blueprint_id)
        if raw is None or raw["version"] != expected_version:
            return None
        raw["spec_dict"] = copy.deepcopy(spec)
        raw["rid_refs"] = rid_refs
        raw["version"] += 1
        return raw["version"]

    def set_metadata(self, blueprint_id, metadata) -> bool:
        if blueprint_id not in self._store:
            return False
        self._store[blueprint_id]["metadata"] = metadata
        return True

    def delete(self, blueprint_id) -> bool:
        return self._store.pop(blueprint_id, None) is not None

    def delete_by_identity(self, identity) -> int:
        return 0

    def load(self, blueprint_id) -> Optional[BlueprintDocument]:
        raw = self._store.get(blueprint_id)
        if raw is None:
            return None
        return BlueprintDocument.model_validate(raw)

    def load_many(self, blueprint_ids) -> List[BlueprintDocument]:
        return [self.load(bid) for bid in blueprint_ids if bid in self._store]

    def exists(self, blueprint_id) -> bool:
        return blueprint_id in self._store

    def list_ids(self, identity=None, skip=0, limit=20, sort_desc=True):
        return list(self._store.keys())[skip : skip + limit]

    def list_docs(self, identity=None, skip=0, limit=20, sort_desc=True):
        return [self.load(bid) for bid in list(self._store.keys())[skip : skip + limit]]

    def list_summaries(self, identity=None, skip=0, limit=20, sort_desc=True):
        return []

    def count(self, identity=None) -> int:
        return len(self._store)

    def list_direct_usage(self, rid):
        return []

    def count_usage(self, rid) -> int:
        return 0


class _FakeVersionRepo(BlueprintVersionRepository):
    def __init__(self, fail_on_duplicate: bool = False):
        self._store: List[BlueprintVersionDocument] = []
        self._fail_on_duplicate = fail_on_duplicate
        self.insert_calls: List[BlueprintVersionDocument] = []

    def insert_snapshot(self, version_doc: BlueprintVersionDocument) -> str:
        self.insert_calls.append(version_doc)
        for existing in self._store:
            if (
                existing.blueprint_id == version_doc.blueprint_id
                and existing.version == version_doc.version
            ):
                if self._fail_on_duplicate:
                    raise DuplicateSnapshotError(
                        blueprint_id=version_doc.blueprint_id,
                        version=version_doc.version,
                    )
                return f"dup-{version_doc.version}"
        self._store.append(version_doc)
        return f"id-{len(self._store)}"

    def find_by_blueprint_id(
        self, blueprint_id: str, page: int = 1, page_size: int = 20
    ) -> Tuple[List[BlueprintVersionDocument], int]:
        matching = sorted(
            [v for v in self._store if v.blueprint_id == blueprint_id],
            key=lambda v: v.version,
            reverse=True,
        )
        total = len(matching)
        skip = (page - 1) * page_size
        return matching[skip : skip + page_size], total

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

SPEC_A = {"name": "Spec A"}
SPEC_B = {"name": "Spec B"}


@pytest.fixture()
def bp_repo():
    r = _FakeBPRepo()
    r._seed("bp-1", SPEC_A, version=1)
    return r


@pytest.fixture()
def ver_repo():
    return _FakeVersionRepo()


@pytest.fixture()
def svc(bp_repo, ver_repo):
    return BlueprintService(repo=bp_repo, version_repo=ver_repo)


@pytest.fixture()
def svc_no_ver(bp_repo):
    return BlueprintService(repo=bp_repo)


# ===========================================================================
# _require_version_repo guard
# ===========================================================================


class TestRequireVersionRepo:
    def test_list_versions_without_repo_raises_runtime(self, svc_no_ver):
        with pytest.raises(RuntimeError, match="BlueprintVersionRepository"):
            svc_no_ver.list_versions("bp-1")

    def test_load_version_without_repo_raises_runtime(self, svc_no_ver):
        with pytest.raises(RuntimeError, match="BlueprintVersionRepository"):
            svc_no_ver.load_version("bp-1", 1)

    def test_restore_version_without_repo_raises_runtime(self, svc_no_ver):
        with pytest.raises(RuntimeError, match="BlueprintVersionRepository"):
            svc_no_ver.restore_version("bp-1", target_version=1)


# ===========================================================================
# list_versions — page / page_size clamping
# ===========================================================================


class TestListVersionsPagingBoundaries:
    def _seed_versions(self, ver_repo, blueprint_id, count):
        for v in range(1, count + 1):
            ver_repo._store.append(
                BlueprintVersionDocument(
                    blueprint_id=blueprint_id,
                    version=v,
                    spec_dict_snapshot={"v": v},
                )
            )

    def test_page_zero_clamped_to_1(self, svc):
        result = svc.list_versions("bp-1", page=0)
        assert result["page"] == 1

    def test_negative_page_clamped_to_1(self, svc):
        result = svc.list_versions("bp-1", page=-5)
        assert result["page"] == 1

    def test_page_size_above_100_clamped(self, svc):
        result = svc.list_versions("bp-1", page_size=200)
        assert result["page_size"] == 100

    def test_page_size_zero_clamped_to_1(self, svc, ver_repo):
        self._seed_versions(ver_repo, "bp-1", 3)
        result = svc.list_versions("bp-1", page_size=0)
        assert result["page_size"] == 1

    def test_page_size_negative_clamped_to_1(self, svc, ver_repo):
        self._seed_versions(ver_repo, "bp-1", 2)
        result = svc.list_versions("bp-1", page_size=-3)
        assert result["page_size"] == 1

    def test_total_pages_calculated_correctly(self, svc, ver_repo):
        self._seed_versions(ver_repo, "bp-1", 7)
        result = svc.list_versions("bp-1", page=1, page_size=3)
        assert result["total_pages"] == 3  # ceil(7/3)

    def test_total_pages_exact_division(self, svc, ver_repo):
        self._seed_versions(ver_repo, "bp-1", 6)
        result = svc.list_versions("bp-1", page=1, page_size=3)
        assert result["total_pages"] == 2

    def test_empty_history_total_pages_is_0(self, svc):
        result = svc.list_versions("bp-1")
        assert result["total_pages"] == 0


# ===========================================================================
# _snapshot_version idempotency on DuplicateKeyError
# ===========================================================================


class TestSnapshotIdempotency:
    """_snapshot_version must swallow DuplicateKeyError silently."""

    def test_duplicate_snapshot_does_not_raise(self, bp_repo):
        failing_ver_repo = _FakeVersionRepo(fail_on_duplicate=True)
        # Pre-seed a v1 snapshot so the duplicate-on-insert error is triggered
        failing_ver_repo._store.append(
            BlueprintVersionDocument(
                blueprint_id="bp-1",
                version=1,
                spec_dict_snapshot=SPEC_A,
            )
        )
        svc = BlueprintService(repo=bp_repo, version_repo=failing_ver_repo)
        # Should NOT raise even though DuplicateKeyError would fire
        svc.update_draft("bp-1", SPEC_B)


# ===========================================================================
# restore_version — change_summary format
# ===========================================================================


class TestRestoreVersionSummary:
    def test_restore_creates_summary_mentioning_target_version(self, svc, bp_repo, ver_repo):
        ver_repo._store.append(
            BlueprintVersionDocument(
                blueprint_id="bp-1",
                version=1,
                spec_dict_snapshot=SPEC_A,
            )
        )
        bp_repo._store["bp-1"]["version"] = 2
        bp_repo._store["bp-1"]["spec_dict"] = SPEC_B

        svc.restore_version("bp-1", target_version=1, user_id="user:alice")

        # The change_summary on the pre-restore snapshot should mention "version 1"
        summaries = [v.change_summary for v in ver_repo._store]
        assert any("version 1" in (s or "").lower() for s in summaries)

    def test_restore_user_id_propagated_to_snapshot(self, svc, bp_repo, ver_repo):
        ver_repo._store.append(
            BlueprintVersionDocument(
                blueprint_id="bp-1",
                version=1,
                spec_dict_snapshot=SPEC_A,
            )
        )
        bp_repo._store["bp-1"]["version"] = 2
        bp_repo._store["bp-1"]["spec_dict"] = SPEC_B

        svc.restore_version("bp-1", target_version=1, user_id="user:restorer")

        # At least one snapshot should be attributed to the restorer
        creators = [v.created_by for v in ver_repo._store]
        assert "user:restorer" in creators


# ===========================================================================
# _extract_rid_refs — edge cases
# ===========================================================================


class TestExtractRidRefsEdgeCases:
    def test_empty_dict_returns_empty_list(self, svc):
        assert svc._extract_rid_refs({}) == []

    def test_none_values_skipped(self, svc):
        result = svc._extract_rid_refs({"x": None, "y": {"z": None}})
        assert result == []

    def test_non_string_ref_values_skipped(self, svc):
        result = svc._extract_rid_refs({"a": {"$ref": 123}})
        assert result == []

    def test_deeply_nested_list_refs_found(self, svc):
        draft = {"levels": [[{"deep": {"$ref": "nested-ref"}}]]}
        refs = svc._extract_rid_refs(draft)
        assert "nested-ref" in refs

    def test_mixed_refs_and_non_refs(self, svc):
        draft = {
            "nodes": [
                {"config": {"$ref": "r1"}, "name": "Step 1"},
                {"config": {"not_ref": "r2"}, "name": "Step 2"},
            ]
        }
        refs = svc._extract_rid_refs(draft)
        assert refs == ["r1"]


# ===========================================================================
# update_draft — legacy path (no version_repo) boundary cases
# ===========================================================================


class TestUpdateDraftLegacyPath:
    """update_draft now requires version_repo — calls without it must fail."""

    def test_raises_runtime_error_without_version_repo(self, svc_no_ver):
        with pytest.raises(RuntimeError, match="BlueprintVersionRepository"):
            svc_no_ver.update_draft("bp-1", {"new": "spec"})
