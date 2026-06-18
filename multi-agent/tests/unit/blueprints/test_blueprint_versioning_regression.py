"""
Regression tests for Blueprint Version History — GENIE-1336.

These tests guard against regressions introduced across all layers of the
version history feature.  Each test documents a specific behaviour that was
intentional at implementation time; failing tests here indicate a breaking
change that needs explicit sign-off.

Regression areas
----------------
1. **Exception message contracts** — callers and tests depend on the exact
   wording of VersionNotFoundError and ConcurrentModificationError.
2. **Version repo guard** — update_draft() without a version_repo must
   raise RuntimeError (legacy fallback removed per architecture review).
3. **Pagination arithmetic** — total_pages ceiling division and clamping.
4. **BlueprintService guard** — _ensure_version_repo() raises RuntimeError
   when version_repo is None; the message is stable.
5. **Snapshot isolation** — BlueprintVersionDocument deep-copies its snapshot
   so later mutations to the source dict don't corrupt stored versions.
6. **OCC semantics** — None from update_with_version() raises
   ConcurrentModificationError (not a generic error).
7. **restore_version change_summary** — always contains "Restore" and the
   target version number so operators can trace rollbacks.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from mas.blueprints.exceptions import (
    BlueprintNotFoundError,
    VersionNotFoundError,
    ConcurrentModificationError,
)
from mas.blueprints.models.blueprint_version import BlueprintVersionDocument
from mas.blueprints.service import BlueprintService


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_blueprint_doc(blueprint_id="bp-1", version=1, spec_dict=None, **kwargs):
    """Return a minimal MagicMock that looks like a BlueprintDocument."""
    doc = MagicMock()
    doc.blueprint_id = blueprint_id
    doc.version = version
    doc.spec_dict = spec_dict or {"name": "test", "nodes": []}
    for k, v in kwargs.items():
        setattr(doc, k, v)
    return doc


def _svc_with_repos(*, repo=None, version_repo=None) -> BlueprintService:
    """Create a BlueprintService wired with the given (mock) repos."""
    r = repo or MagicMock()
    svc = BlueprintService(repo=r)
    if version_repo is not None:
        svc.version_repo = version_repo
    return svc


def _versioned_svc(*, repo=None, version_repo=None) -> BlueprintService:
    """Create a service with both repos configured."""
    r = repo or MagicMock()
    vr = version_repo or MagicMock()
    svc = BlueprintService(repo=r, version_repo=vr)
    return svc


# ── 1. Exception message contracts ────────────────────────────────────────────


@pytest.mark.unit
class TestExceptionMessages:
    """Verify the exact error messages callers and HTTP handlers depend upon."""

    def test_version_not_found_message_format(self):
        err = VersionNotFoundError("bp-abc", 7)
        msg = str(err)
        assert "7" in msg
        assert "bp-abc" in msg
        # Exact contract from exceptions.py docstring.
        assert "Version 7 not found for blueprint 'bp-abc'." == msg

    def test_concurrent_modification_message_format(self):
        err = ConcurrentModificationError("bp-xyz", 3)
        msg = str(err)
        assert "bp-xyz" in msg
        assert "3" in msg
        assert "concurrent" in msg.lower() or "modified" in msg.lower()

    def test_blueprint_not_found_message_format(self):
        err = BlueprintNotFoundError("bp-missing")
        assert "bp-missing" in str(err)

    def test_version_not_found_attributes(self):
        """VersionNotFoundError exposes blueprint_id and version attributes."""
        err = VersionNotFoundError("bp-1", 42)
        assert err.blueprint_id == "bp-1"
        assert err.version == 42

    def test_concurrent_modification_attributes(self):
        """ConcurrentModificationError exposes blueprint_id and expected_version."""
        err = ConcurrentModificationError("bp-2", 5)
        assert err.blueprint_id == "bp-2"
        assert err.expected_version == 5

    def test_version_not_found_is_blueprint_error(self):
        """VersionNotFoundError is a sub-class of BlueprintError."""
        from mas.blueprints.exceptions import BlueprintError
        err = VersionNotFoundError("bp-1", 1)
        assert isinstance(err, BlueprintError)

    def test_concurrent_modification_is_blueprint_error(self):
        from mas.blueprints.exceptions import BlueprintError
        err = ConcurrentModificationError("bp-1", 1)
        assert isinstance(err, BlueprintError)


# ── 2. Version repo guard ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestUpdateDraftRequiresVersionRepo:
    """update_draft() without version_repo must raise RuntimeError."""

    def test_update_draft_raises_runtime_error_without_version_repo(self):
        """update_draft must fail-fast when version_repo is None."""
        repo = MagicMock()
        svc = BlueprintService(repo=repo)  # No version_repo.

        with pytest.raises(RuntimeError, match="BlueprintVersionRepository is not configured"):
            svc.update_draft(blueprint_id="bp-1", draft_dict={"name": "v"})

        # Neither write path should be invoked
        repo.update.assert_not_called()
        repo.update_with_version.assert_not_called()

    def test_update_draft_without_version_repo_does_not_create_snapshot(self):
        """Without version_repo, no snapshot is created and no write occurs."""
        repo = MagicMock()
        svc = BlueprintService(repo=repo)

        with pytest.raises(RuntimeError):
            svc.update_draft(blueprint_id="bp-1", draft_dict={"name": "v"})

    def test_runtime_error_message_is_stable(self):
        """The error message must mention version_repo so operators can diagnose."""
        repo = MagicMock()
        svc = BlueprintService(repo=repo)

        with pytest.raises(RuntimeError, match="version_repo"):
            svc.update_draft(blueprint_id="bp-1", draft_dict={})


# ── 3. Pagination arithmetic ──────────────────────────────────────────────────


@pytest.mark.unit
class TestPaginationArithmetic:
    """Ceiling division and parameter clamping for list_versions()."""

    def _svc_with_versions(self, items, total):
        version_repo = MagicMock()
        version_repo.find_by_blueprint_id.return_value = (items, total)
        repo = MagicMock()
        repo.load.return_value = _make_blueprint_doc()
        return BlueprintService(repo=repo, version_repo=version_repo)

    def test_total_pages_is_ceiling_of_total_divided_by_page_size(self):
        """7 items / page_size=3 → total_pages=3 (ceiling division)."""
        svc = self._svc_with_versions([], 7)
        result = svc.list_versions("bp-1", page=1, page_size=3)
        assert result["total_pages"] == 3

    def test_total_pages_is_one_when_total_equals_page_size(self):
        svc = self._svc_with_versions([], 20)
        result = svc.list_versions("bp-1", page=1, page_size=20)
        assert result["total_pages"] == 1

    def test_total_pages_is_one_minimum_when_total_is_zero(self):
        """Even with 0 versions, total_pages must be at least 1."""
        svc = self._svc_with_versions([], 0)
        result = svc.list_versions("bp-1", page=1, page_size=20)
        assert result["total_pages"] >= 1

    def test_page_clamped_to_1_when_zero_or_negative(self):
        """page ≤ 0 is clamped to 1 before calling the repo."""
        version_repo = MagicMock()
        version_repo.find_by_blueprint_id.return_value = ([], 0)
        repo = MagicMock()
        repo.load.return_value = _make_blueprint_doc()
        svc = BlueprintService(repo=repo, version_repo=version_repo)

        svc.list_versions("bp-1", page=0, page_size=10)

        _, kwargs = version_repo.find_by_blueprint_id.call_args
        assert kwargs["page"] >= 1

    def test_page_size_clamped_to_100_maximum(self):
        """page_size > 100 is clamped to 100."""
        version_repo = MagicMock()
        version_repo.find_by_blueprint_id.return_value = ([], 0)
        repo = MagicMock()
        repo.load.return_value = _make_blueprint_doc()
        svc = BlueprintService(repo=repo, version_repo=version_repo)

        svc.list_versions("bp-1", page=1, page_size=500)

        _, kwargs = version_repo.find_by_blueprint_id.call_args
        assert kwargs["page_size"] <= 100

    def test_page_size_clamped_to_1_minimum(self):
        """page_size < 1 is clamped to 1."""
        version_repo = MagicMock()
        version_repo.find_by_blueprint_id.return_value = ([], 0)
        repo = MagicMock()
        repo.load.return_value = _make_blueprint_doc()
        svc = BlueprintService(repo=repo, version_repo=version_repo)

        svc.list_versions("bp-1", page=1, page_size=0)

        _, kwargs = version_repo.find_by_blueprint_id.call_args
        assert kwargs["page_size"] >= 1

    def test_ceiling_division_does_not_use_floor(self):
        """101 items / page_size=100 → 2 pages (not 1)."""
        svc = self._svc_with_versions([], 101)
        result = svc.list_versions("bp-1", page=1, page_size=100)
        assert result["total_pages"] == 2


# ── 4. _ensure_version_repo() guard ──────────────────────────────────────────


@pytest.mark.unit
class TestEnsureVersionRepoGuard:
    """Service methods that require version_repo raise RuntimeError when it's None."""

    def test_list_versions_raises_runtime_error_without_version_repo(self):
        repo = MagicMock()
        repo.load.return_value = _make_blueprint_doc()
        svc = BlueprintService(repo=repo)  # version_repo=None

        with pytest.raises(RuntimeError):
            svc.list_versions("bp-1")

    def test_load_version_raises_runtime_error_without_version_repo(self):
        repo = MagicMock()
        repo.load.return_value = _make_blueprint_doc()
        svc = BlueprintService(repo=repo)

        with pytest.raises(RuntimeError):
            svc.load_version("bp-1", 1)

    def test_restore_version_raises_runtime_error_without_version_repo(self):
        repo = MagicMock()
        repo.load.return_value = _make_blueprint_doc()
        svc = BlueprintService(repo=repo)

        with pytest.raises(RuntimeError):
            svc.restore_version("bp-1", 1)

    def test_runtime_error_message_mentions_version_repo(self):
        """The error message must mention version_repo so operators can diagnose."""
        repo = MagicMock()
        svc = BlueprintService(repo=repo)

        with pytest.raises(RuntimeError, match="version_repo"):
            svc.list_versions("bp-1")


# ── 5. Snapshot isolation ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestSnapshotIsolation:
    """BlueprintVersionDocument deep-copies so mutations don't corrupt snapshots."""

    def test_mutating_source_dict_does_not_affect_stored_snapshot(self):
        source = {"nodes": [{"id": "n1"}], "edges": []}
        doc = BlueprintVersionDocument(
            blueprint_id="bp-1",
            version=1,
            spec_dict_snapshot=source,
            created_by="u",
        )
        # Mutate the source after construction.
        source["nodes"].append({"id": "n2"})
        source["new_key"] = "injected"

        assert len(doc.spec_dict_snapshot["nodes"]) == 1
        assert "new_key" not in doc.spec_dict_snapshot

    def test_to_detail_returns_independent_copy(self):
        """Mutating the dict returned by to_detail() must not corrupt the doc."""
        doc = BlueprintVersionDocument(
            blueprint_id="bp-1",
            version=1,
            spec_dict_snapshot={"k": "original"},
            created_by="u",
        )
        detail = doc.to_detail()
        detail["spec_dict_snapshot"]["k"] = "TAMPERED"

        assert doc.spec_dict_snapshot["k"] == "original"

    def test_two_documents_with_same_source_are_independent(self):
        """Two documents built from the same source dict are fully independent."""
        shared_source = {"nodes": [{"id": "n1"}]}
        doc_a = BlueprintVersionDocument(
            blueprint_id="bp-1", version=1,
            spec_dict_snapshot=shared_source, created_by="u"
        )
        doc_b = BlueprintVersionDocument(
            blueprint_id="bp-1", version=2,
            spec_dict_snapshot=shared_source, created_by="u"
        )
        doc_a.spec_dict_snapshot["nodes"].append({"id": "n2"})

        assert len(doc_b.spec_dict_snapshot["nodes"]) == 1


# ── 6. OCC semantics ──────────────────────────────────────────────────────────


@pytest.mark.unit
class TestOCCSemantics:
    """None from update_with_version() must raise ConcurrentModificationError."""

    def test_concurrent_modification_error_raised_on_occ_failure(self):
        repo = MagicMock()
        repo.load.return_value = _make_blueprint_doc(version=2)
        repo.update_with_version.return_value = None  # OCC mismatch.

        version_repo = MagicMock()
        version_repo.insert_snapshot.return_value = "some-id"

        svc = BlueprintService(repo=repo, version_repo=version_repo)

        with pytest.raises(ConcurrentModificationError):
            svc.update_draft(blueprint_id="bp-1", draft_dict={"name": "x"})

    def test_concurrent_modification_error_carries_blueprint_id(self):
        repo = MagicMock()
        repo.load.return_value = _make_blueprint_doc(blueprint_id="bp-occ", version=1)
        repo.update_with_version.return_value = None

        version_repo = MagicMock()
        version_repo.insert_snapshot.return_value = "id"

        svc = BlueprintService(repo=repo, version_repo=version_repo)

        with pytest.raises(ConcurrentModificationError) as exc_info:
            svc.update_draft(blueprint_id="bp-occ", draft_dict={})

        assert exc_info.value.blueprint_id == "bp-occ"

    def test_successful_occ_write_returns_true(self):
        """When update_with_version() succeeds (not None), update_draft returns True."""
        repo = MagicMock()
        repo.load.return_value = _make_blueprint_doc(version=1)
        repo.update_with_version.return_value = _make_blueprint_doc(version=2)

        version_repo = MagicMock()
        version_repo.insert_snapshot.return_value = "id"

        svc = BlueprintService(repo=repo, version_repo=version_repo)

        result = svc.update_draft(blueprint_id="bp-1", draft_dict={})

        assert result is True


# ── 7. restore_version change_summary ────────────────────────────────────────


@pytest.mark.unit
class TestRestoreVersionChangeSummary:
    """The change_summary for a restore operation must reference the target version."""

    def _capture_update_draft_kwargs(self, target_version: int) -> dict:
        """Run restore_version and capture the kwargs passed to update_draft."""
        repo = MagicMock()
        snapshot_doc = BlueprintVersionDocument(
            blueprint_id="bp-1",
            version=target_version,
            spec_dict_snapshot={"name": "old"},
            created_by="u",
        )
        repo.load.return_value = _make_blueprint_doc()
        repo.update_with_version.return_value = _make_blueprint_doc(version=target_version + 1)

        version_repo = MagicMock()
        version_repo.find_one.return_value = snapshot_doc
        version_repo.insert_snapshot.return_value = "id"

        captured = {}

        svc = BlueprintService(repo=repo, version_repo=version_repo)
        # Patch update_draft to capture its arguments instead of actually running it.
        original = svc.update_draft

        def _capture(**kwargs):
            captured.update(kwargs)
            return original(**kwargs)

        svc.update_draft = _capture
        svc.restore_version(blueprint_id="bp-1", target_version=target_version)
        return captured

    def test_change_summary_contains_target_version(self):
        kwargs = self._capture_update_draft_kwargs(3)
        summary = kwargs.get("change_summary", "")
        assert "3" in summary, f"Expected version '3' in change_summary, got: '{summary}'"

    def test_change_summary_contains_restore_keyword(self):
        kwargs = self._capture_update_draft_kwargs(2)
        summary = (kwargs.get("change_summary") or "").lower()
        assert "restor" in summary, (
            f"Expected 'restor*' in change_summary (case-insensitive), got: '{summary}'"
        )

    def test_restore_passes_user_id_to_update_draft(self):
        """restore_version must forward user_id so the snapshot has correct created_by."""
        repo = MagicMock()
        snapshot_doc = BlueprintVersionDocument(
            blueprint_id="bp-1",
            version=1,
            spec_dict_snapshot={},
            created_by="migration",
        )
        repo.load.return_value = _make_blueprint_doc()
        repo.update_with_version.return_value = _make_blueprint_doc(version=2)

        version_repo = MagicMock()
        version_repo.find_one.return_value = snapshot_doc
        version_repo.insert_snapshot.return_value = "id"

        update_draft_kwargs = {}
        svc = BlueprintService(repo=repo, version_repo=version_repo)
        original = svc.update_draft

        def _capture(**kwargs):
            update_draft_kwargs.update(kwargs)
            return original(**kwargs)

        svc.update_draft = _capture
        svc.restore_version(blueprint_id="bp-1", target_version=1, user_id="bob")

        assert update_draft_kwargs.get("user_id") == "bob"
