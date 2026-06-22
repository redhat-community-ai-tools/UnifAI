"""
Unit tests for BlueprintService versioning methods — GENIE-1336.

Isolated at the service layer: both BlueprintRepository and
BlueprintVersionRepository are replaced with MagicMock instances.

Covered surface:
  - update_draft()  — version_repo required, versioned, OCC failure, snapshot skip
  - list_versions() — happy path, pagination clamp, blueprint-not-found, no-version-repo
  - load_version()  — happy path, blueprint-not-found, version-not-found, no-version-repo
  - restore_version() — delegates to update_draft(), version-not-found propagation
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

from mas.blueprints.service import BlueprintService
from mas.blueprints.models.blueprint_version import BlueprintVersionDocument
from mas.blueprints.models.blueprint import BlueprintDocument, BlueprintDraft
from mas.blueprints.exceptions import (
    BlueprintNotFoundError,
    ConcurrentModificationError,
    DuplicateSnapshotError,
    FeatureNotConfiguredError,
    VersionNotFoundError,
)


# ── Test fixtures ──────────────────────────────────────────────────────────────


def _make_blueprint_doc(
    blueprint_id: str = "bp-1",
    version: int = 1,
    spec_dict: dict | None = None,
) -> BlueprintDocument:
    """Construct a minimal BlueprintDocument for mocking .load() returns."""
    doc = MagicMock(spec=BlueprintDocument)
    doc.blueprint_id = blueprint_id
    doc.version = version
    doc.spec_dict = spec_dict or {"name": "Test Blueprint", "nodes": []}
    return doc


def _make_version_doc(
    blueprint_id: str = "bp-1",
    version: int = 1,
    spec_dict_snapshot: dict | None = None,
    created_by: str = "user",
) -> BlueprintVersionDocument:
    return BlueprintVersionDocument(
        blueprint_id=blueprint_id,
        version=version,
        spec_dict_snapshot=spec_dict_snapshot or {},
        created_by=created_by,
        created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )


def _make_service(
    *,
    repo: MagicMock | None = None,
    version_repo: MagicMock | None = None,
) -> BlueprintService:
    """Wire a BlueprintService with mock dependencies.

    A bare minimum mock resolver is provided so RefWalker calls succeed.
    """
    repo = repo or MagicMock()
    resolver = MagicMock()
    svc = BlueprintService(
        repo=repo,
        resolver=resolver,
        version_repo=version_repo,
    )
    return svc


# ── update_draft — version_repo required ─────────────────────────────────────


@pytest.mark.unit
class TestUpdateDraftRequiresVersionRepo:
    """update_draft raises FeatureNotConfiguredError when version_repo is not configured."""

    def test_raises_feature_not_configured_when_version_repo_is_none(self):
        repo = MagicMock()
        svc = _make_service(repo=repo, version_repo=None)

        with pytest.raises(FeatureNotConfiguredError):
            svc.update_draft(
                blueprint_id="bp-1",
                draft_dict={"name": "Updated", "nodes": []},
            )

        # Neither write path should be invoked
        repo.update.assert_not_called()
        repo.update_with_version.assert_not_called()


# ── update_draft — versioned path (with version_repo) ─────────────────────────


@pytest.mark.unit
class TestUpdateDraftVersionedPath:
    """When version_repo is present, OCC + snapshot logic is exercised."""

    def _setup(self, current_version: int = 3):
        repo = MagicMock()
        version_repo = MagicMock()

        current_doc = _make_blueprint_doc(version=current_version, spec_dict={"name": "Old", "nodes": []})
        repo.load.return_value = current_doc

        # update_with_version succeeds by default (returns a new doc)
        new_doc = _make_blueprint_doc(version=current_version + 1)
        repo.update_with_version.return_value = new_doc

        svc = _make_service(repo=repo, version_repo=version_repo)
        return svc, repo, version_repo, current_doc

    def test_inserts_snapshot_of_current_doc(self):
        svc, repo, version_repo, current_doc = self._setup(current_version=5)

        svc.update_draft(
            blueprint_id="bp-1",
            draft_dict={"name": "New", "nodes": []},
            user_id="alice",
            change_summary="Refactored",
        )

        version_repo.insert_snapshot.assert_called_once()
        snapshot: BlueprintVersionDocument = version_repo.insert_snapshot.call_args.args[0]
        assert snapshot.blueprint_id == "bp-1"
        assert snapshot.version == 5  # Snapshot of the BEFORE state
        assert snapshot.created_by == "alice"
        assert snapshot.change_summary == "Refactored"

    def test_calls_update_with_version_using_expected_version(self):
        svc, repo, _, _ = self._setup(current_version=7)

        svc.update_draft(
            blueprint_id="bp-1",
            draft_dict={"name": "New", "nodes": []},
        )

        repo.update_with_version.assert_called_once()
        kwargs = repo.update_with_version.call_args.kwargs
        assert kwargs["blueprint_id"] == "bp-1"
        assert kwargs["expected_version"] == 7

    def test_returns_true_on_success(self):
        svc, _, _, _ = self._setup()
        result = svc.update_draft(blueprint_id="bp-1", draft_dict={"name": "N", "nodes": []})
        assert result is True

    def test_raises_concurrent_modification_when_update_returns_none(self):
        svc, repo, _, _ = self._setup(current_version=3)
        repo.update_with_version.return_value = None  # OCC miss

        with pytest.raises(ConcurrentModificationError) as exc_info:
            svc.update_draft(blueprint_id="bp-1", draft_dict={"name": "N", "nodes": []})

        assert exc_info.value.blueprint_id == "bp-1"
        assert exc_info.value.expected_version == 3

    def test_snapshot_failure_is_logged_but_not_re_raised(self):
        """A DuplicateSnapshotError on insert_snapshot is swallowed — OCC write still proceeds."""
        svc, repo, version_repo, _ = self._setup(current_version=2)
        version_repo.insert_snapshot.side_effect = DuplicateSnapshotError(
            blueprint_id="bp-1", version=2
        )

        # Should NOT raise despite snapshot failure
        result = svc.update_draft(blueprint_id="bp-1", draft_dict={"name": "N", "nodes": []})
        assert result is True
        repo.update_with_version.assert_called_once()

    def test_raises_blueprint_not_found_when_load_raises(self):
        repo = MagicMock()
        repo.load.side_effect = KeyError("bp-404")
        svc = _make_service(repo=repo, version_repo=MagicMock())

        with pytest.raises(BlueprintNotFoundError):
            svc.update_draft(blueprint_id="bp-404", draft_dict={"name": "X", "nodes": []})


# ── list_versions ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestListVersions:
    """BlueprintService.list_versions() — pagination, validation, error paths."""

    def _svc(self, *, exists: bool = True, total: int = 5, items=None):
        repo = MagicMock()
        repo.exists.return_value = exists
        version_repo = MagicMock()
        items = items or [_make_version_doc(version=i) for i in range(1, total + 1)]
        version_repo.find_by_blueprint_id.return_value = (items, total)

        return _make_service(repo=repo, version_repo=version_repo), repo, version_repo

    def test_happy_path_returns_correct_shape(self):
        svc, _, _ = self._svc(total=3)
        result = svc.list_versions("bp-1", page=1, page_size=10)

        assert "items" in result
        assert "total" in result
        assert "page" in result
        assert "page_size" in result
        assert "total_pages" in result

    def test_total_pages_is_ceiling_division(self):
        svc, _, _ = self._svc(total=25)
        result = svc.list_versions("bp-1", page=1, page_size=10)
        assert result["total_pages"] == 3  # ceil(25 / 10)

    def test_total_pages_minimum_is_one_when_empty(self):
        svc, _, _ = self._svc(total=0, items=[])
        result = svc.list_versions("bp-1", page=1, page_size=10)
        assert result["total_pages"] == 1

    def test_page_clamped_to_minimum_one(self):
        svc, _, version_repo = self._svc(total=5)
        result = svc.list_versions("bp-1", page=0, page_size=10)

        # Internal call must use page=1 (clamped)
        _, call_kwargs = version_repo.find_by_blueprint_id.call_args
        assert call_kwargs["page"] == 1

    def test_page_size_clamped_to_100_max(self):
        svc, _, version_repo = self._svc(total=5)
        svc.list_versions("bp-1", page=1, page_size=999)

        _, call_kwargs = version_repo.find_by_blueprint_id.call_args
        assert call_kwargs["page_size"] == 100

    def test_page_size_clamped_to_minimum_one(self):
        svc, _, version_repo = self._svc(total=5)
        svc.list_versions("bp-1", page=1, page_size=0)

        _, call_kwargs = version_repo.find_by_blueprint_id.call_args
        assert call_kwargs["page_size"] == 1

    def test_items_are_summaries(self):
        """Each item in result['items'] must be a summary dict (no spec_dict_snapshot)."""
        svc, _, _ = self._svc(total=2)
        result = svc.list_versions("bp-1", page=1, page_size=10)

        for item in result["items"]:
            assert "spec_dict_snapshot" not in item
            assert "version" in item

    def test_raises_blueprint_not_found_when_blueprint_absent(self):
        svc, _, _ = self._svc(exists=False)
        with pytest.raises(BlueprintNotFoundError) as exc_info:
            svc.list_versions("bp-nope", page=1)

        assert exc_info.value.blueprint_id == "bp-nope"

    def test_raises_feature_not_configured_when_version_repo_not_configured(self):
        svc = _make_service(repo=MagicMock(), version_repo=None)
        with pytest.raises(FeatureNotConfiguredError):
            svc.list_versions("bp-1")


# ── load_version ───────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestLoadVersion:
    """BlueprintService.load_version() — happy path and error paths."""

    def _svc(self, *, exists: bool = True, version_doc=None):
        repo = MagicMock()
        repo.exists.return_value = exists
        version_repo = MagicMock()
        version_repo.find_one.return_value = version_doc
        return _make_service(repo=repo, version_repo=version_repo), version_repo

    def test_happy_path_returns_detail_dict(self):
        vdoc = _make_version_doc(blueprint_id="bp-1", version=4, spec_dict_snapshot={"k": "v"})
        svc, _ = self._svc(version_doc=vdoc)

        result = svc.load_version("bp-1", 4)

        assert result["version"] == 4
        assert result["blueprint_id"] == "bp-1"
        assert result["spec_dict_snapshot"] == {"k": "v"}

    def test_raises_blueprint_not_found_when_blueprint_absent(self):
        svc, _ = self._svc(exists=False)
        with pytest.raises(BlueprintNotFoundError) as exc_info:
            svc.load_version("bp-gone", 1)

        assert exc_info.value.blueprint_id == "bp-gone"

    def test_raises_version_not_found_when_snapshot_absent(self):
        svc, _ = self._svc(exists=True, version_doc=None)
        with pytest.raises(VersionNotFoundError) as exc_info:
            svc.load_version("bp-1", 99)

        assert exc_info.value.blueprint_id == "bp-1"
        assert exc_info.value.version == 99

    def test_raises_feature_not_configured_when_version_repo_not_configured(self):
        svc = _make_service(repo=MagicMock(), version_repo=None)
        with pytest.raises(FeatureNotConfiguredError):
            svc.load_version("bp-1", 1)

    def test_passes_correct_args_to_find_one(self):
        vdoc = _make_version_doc()
        svc, version_repo = self._svc(version_doc=vdoc)

        svc.load_version("bp-target", 7)
        version_repo.find_one.assert_called_once_with("bp-target", 7)


# ── restore_version ────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRestoreVersion:
    """BlueprintService.restore_version() — delegates to update_draft()."""

    def _setup(self, target_spec: dict | None = None, exists: bool = True):
        repo = MagicMock()
        version_repo = MagicMock()

        # Blueprint exists in the main collection
        current_doc = _make_blueprint_doc(version=5)
        repo.load.return_value = current_doc
        repo.exists.return_value = exists

        # The historic version snapshot to restore
        target = _make_version_doc(
            blueprint_id="bp-1",
            version=2,
            spec_dict_snapshot=target_spec or {"name": "Old Version", "nodes": []},
        )
        version_repo.find_one.return_value = target

        # The OCC write succeeds
        new_doc = _make_blueprint_doc(version=6)
        repo.update_with_version.return_value = new_doc

        svc = _make_service(repo=repo, version_repo=version_repo)
        return svc, repo, version_repo

    def test_returns_true_on_success(self):
        svc, _, _ = self._setup()
        result = svc.restore_version("bp-1", target_version=2, user_id="bob")
        assert result is True

    def test_restores_spec_from_historic_snapshot(self):
        """The restore must pass the historic snapshot's spec_dict to update_draft()."""
        historic_spec = {"name": "Restored Name", "nodes": [{"id": "n1"}]}
        svc, repo, version_repo = self._setup(target_spec=historic_spec)

        svc.restore_version("bp-1", target_version=2, user_id="carol")

        # update_with_version is called with the historic spec's content
        # (RefWalker parses it, then it's passed to update_with_version)
        repo.update_with_version.assert_called_once()
        call_kwargs = repo.update_with_version.call_args.kwargs
        assert call_kwargs["blueprint_id"] == "bp-1"

    def test_change_summary_contains_restored_version_number(self):
        """Snapshot inserted during restore should mention the target version."""
        svc, _, version_repo = self._setup()
        svc.restore_version("bp-1", target_version=3, user_id="u")

        insert_call = version_repo.insert_snapshot.call_args.args[0]
        assert insert_call.change_summary is not None
        assert "3" in insert_call.change_summary

    def test_raises_version_not_found_when_snapshot_absent(self):
        svc, _, version_repo = self._setup()
        version_repo.find_one.return_value = None  # Override: snapshot not found

        with pytest.raises(VersionNotFoundError) as exc_info:
            svc.restore_version("bp-1", target_version=99)

        assert exc_info.value.version == 99

    def test_raises_feature_not_configured_when_version_repo_not_configured(self):
        svc = _make_service(repo=MagicMock(), version_repo=None)
        with pytest.raises(FeatureNotConfiguredError):
            svc.restore_version("bp-1", target_version=1)

    def test_propagates_concurrent_modification_error(self):
        """If the OCC write fails during restore, ConcurrentModificationError bubbles up."""
        svc, repo, _ = self._setup()
        repo.update_with_version.return_value = None  # Simulate concurrent modification

        with pytest.raises(ConcurrentModificationError) as exc_info:
            svc.restore_version("bp-1", target_version=2)

        assert exc_info.value.blueprint_id == "bp-1"

    def test_user_id_is_passed_through_to_snapshot(self):
        svc, _, version_repo = self._setup()
        svc.restore_version("bp-1", target_version=2, user_id="dave")

        # The snapshot inserted before the OCC write should carry dave's user_id
        insert_call = version_repo.insert_snapshot.call_args.args[0]
        assert insert_call.created_by == "dave"
