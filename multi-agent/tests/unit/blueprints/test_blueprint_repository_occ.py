"""
Unit tests for MongoBlueprintRepository.update_with_version (OCC).

Uses mongomock for a hermetic, fast in-memory MongoDB.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

try:
    import mongomock
    MONGOMOCK_AVAILABLE = True
except ImportError:
    MONGOMOCK_AVAILABLE = False

from adapters.outbound.mongo.blueprint_repository import MongoBlueprintRepository
from lib.mas.blueprints.models.blueprint import Identity

pytestmark = pytest.mark.skipif(
    not MONGOMOCK_AVAILABLE, reason="mongomock not installed"
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def col():
    client = mongomock.MongoClient()
    return client["test"]["blueprints"]


@pytest.fixture()
def repo(col) -> MongoBlueprintRepository:
    return MongoBlueprintRepository(col=col)


@pytest.fixture()
def blueprint_id(repo) -> str:
    """Seed a single blueprint at version 1 and return its ID."""
    identity = Identity(type="user", id="alice")
    bid = repo.save(
        identity=identity,
        spec={"name": "Original"},
        rid_refs=[],
    )
    return bid


# ---------------------------------------------------------------------------
# save — initialises version=1
# ---------------------------------------------------------------------------


class TestSaveInitialisesVersion:
    def test_new_blueprint_has_version_1(self, repo, blueprint_id, col):
        doc = col.find_one({"blueprint_id": blueprint_id})
        assert doc["version"] == 1

    def test_load_returns_version_1(self, repo, blueprint_id):
        doc = repo.load(blueprint_id)
        assert doc.version == 1


# ---------------------------------------------------------------------------
# update_with_version — OCC guard
# ---------------------------------------------------------------------------


class TestUpdateWithVersion:
    def test_successful_update_returns_new_version(self, repo, blueprint_id):
        new_version = repo.update_with_version(
            blueprint_id=blueprint_id,
            spec={"name": "Updated"},
            rid_refs=[],
            expected_version=1,
        )
        assert new_version == 2

    def test_spec_is_persisted_after_update(self, repo, blueprint_id):
        repo.update_with_version(
            blueprint_id=blueprint_id,
            spec={"name": "Updated"},
            rid_refs=[],
            expected_version=1,
        )
        doc = repo.load(blueprint_id)
        assert doc.spec_dict["name"] == "Updated"

    def test_version_field_incremented_in_db(self, repo, blueprint_id, col):
        repo.update_with_version(
            blueprint_id=blueprint_id,
            spec={"name": "v2"},
            rid_refs=[],
            expected_version=1,
        )
        raw = col.find_one({"blueprint_id": blueprint_id})
        assert raw["version"] == 2

    def test_wrong_expected_version_returns_none(self, repo, blueprint_id):
        result = repo.update_with_version(
            blueprint_id=blueprint_id,
            spec={"name": "Should not persist"},
            rid_refs=[],
            expected_version=99,  # stale
        )
        assert result is None

    def test_wrong_expected_version_does_not_modify_doc(self, repo, blueprint_id, col):
        repo.update_with_version(
            blueprint_id=blueprint_id,
            spec={"name": "Should not persist"},
            rid_refs=[],
            expected_version=99,
        )
        raw = col.find_one({"blueprint_id": blueprint_id})
        assert raw["spec_dict"]["name"] == "Original"
        assert raw["version"] == 1

    def test_missing_blueprint_returns_none(self, repo):
        result = repo.update_with_version(
            blueprint_id="does-not-exist",
            spec={},
            rid_refs=[],
            expected_version=1,
        )
        assert result is None

    def test_sequential_updates_increment_correctly(self, repo, blueprint_id):
        v2 = repo.update_with_version(
            blueprint_id=blueprint_id,
            spec={"name": "v2"},
            rid_refs=[],
            expected_version=1,
        )
        v3 = repo.update_with_version(
            blueprint_id=blueprint_id,
            spec={"name": "v3"},
            rid_refs=[],
            expected_version=2,
        )
        assert v2 == 2
        assert v3 == 3

    def test_second_writer_loses_occ_race(self, repo, blueprint_id):
        """
        Simulate two concurrent writers who both read version=1.
        The first succeeds; the second must get None (OCC conflict).
        """
        # Writer A wins:
        repo.update_with_version(
            blueprint_id=blueprint_id,
            spec={"name": "writer-A"},
            rid_refs=[],
            expected_version=1,
        )
        # Writer B (stale expected_version=1) loses:
        result_b = repo.update_with_version(
            blueprint_id=blueprint_id,
            spec={"name": "writer-B"},
            rid_refs=[],
            expected_version=1,
        )
        assert result_b is None
        # Writer A's spec should be persisted.
        doc = repo.load(blueprint_id)
        assert doc.spec_dict["name"] == "writer-A"


# ---------------------------------------------------------------------------
# _doc_to_model — backwards compatibility
# ---------------------------------------------------------------------------


class TestDocToModelBackwardsCompat:
    def test_doc_without_version_defaults_to_1(self, col, repo):
        """Legacy docs without 'version' field default to version=1 at load time."""
        col.insert_one({
            "blueprint_id": "legacy-001",
            "identity": {"type": "user", "id": "bob"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "spec_dict": {"name": "Legacy"},
            "rid_refs": [],
            "metadata": {},
            # Note: no 'version' field intentionally
        })
        doc = repo.load("legacy-001")
        assert doc.version == 1
