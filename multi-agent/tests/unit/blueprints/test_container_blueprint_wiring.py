"""
Unit tests for the AppContainer DI wiring (GENIE-1336).

Verifies that:
  1. AppContainer builds a BlueprintService with version_repo injected.
  2. The service exposes list_versions / load_version / restore_version.
  3. Env-var overrides are honoured.
  4. ensure_indexes() is called on the version repository during build.
  5. attach_to_flask_app sets both app.container and app.blueprint_service.

All MongoDB connections are mocked out — these tests do NOT require a
running database.
"""

from __future__ import annotations

import os
import sys

# Ensure workspace root and lib/ are in sys.path for robust import resolution
_file_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.abspath(os.path.join(_file_dir, "../../../.."))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)
_lib_dir = os.path.join(_root_dir, "lib")
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)

from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock, call, patch

import pytest

# We import after patching so pymongo is not required at import time.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_collection(name: str = "col") -> MagicMock:
    col = MagicMock(name=name)
    col.create_index = MagicMock(return_value=name)
    col.find_one_and_update = MagicMock(return_value=None)
    return col


def _make_mock_db(bp_col: MagicMock, ver_col: MagicMock) -> MagicMock:
    db = MagicMock()
    db.__getitem__ = MagicMock(
        side_effect=lambda key: {
            "blueprints": bp_col,
            "blueprint_versions": ver_col,
        }.get(key, MagicMock())
    )
    return db


def _make_mock_mongo_client(db: MagicMock) -> MagicMock:
    client = MagicMock()
    client.__getitem__ = MagicMock(return_value=db)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAppContainerBlueprintWiring:
    """AppContainer must wire BlueprintService with a BlueprintVersionRepository."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        """Clear the AppContainer singleton cache before each test."""
        from bootstrap.container import AppContainer

        AppContainer.reset()
        yield
        AppContainer.reset()

    @patch.dict(
        "os.environ",
        {
            "MONGO_URI": "mongodb://localhost:27017",
            "MONGO_DB": "test_db",
            "BLUEPRINT_COLL": "blueprints",
            "BLUEPRINT_VERSIONS_COLL": "blueprint_versions",
        },
        clear=False,
    )
    def test_service_has_version_repo_attribute(self):
        bp_col = _make_mock_collection("bp_col")
        ver_col = _make_mock_collection("ver_col")
        db = _make_mock_db(bp_col, ver_col)
        mock_client = _make_mock_mongo_client(db)

        with patch("bootstrap.container.MongoClient", return_value=mock_client):
            from bootstrap.container import AppContainer

            container = AppContainer()
            svc = container.blueprint_service

        # The service must have a non-None _version_repo attribute
        assert hasattr(svc, "_version_repo")
        assert svc._version_repo is not None

    @patch.dict(
        "os.environ",
        {
            "MONGO_URI": "mongodb://localhost:27017",
            "MONGO_DB": "test_db",
            "BLUEPRINT_COLL": "blueprints",
            "BLUEPRINT_VERSIONS_COLL": "blueprint_versions",
        },
        clear=False,
    )
    def test_ensure_indexes_called_during_build(self):
        bp_col = _make_mock_collection("bp_col")
        ver_col = _make_mock_collection("ver_col")
        db = _make_mock_db(bp_col, ver_col)
        mock_client = _make_mock_mongo_client(db)

        with patch("bootstrap.container.MongoClient", return_value=mock_client):
            # patch ensure_indexes on the adapter class
            with patch(
                "adapters.outbound.mongo.blueprint_version_repository"
                ".MongoBlueprintVersionRepository.ensure_indexes"
            ) as mock_ensure:
                from bootstrap.container import AppContainer

                AppContainer()
                mock_ensure.assert_called_once()

    @patch.dict(
        "os.environ",
        {
            "MONGO_URI": "mongodb://localhost:27017",
            "MONGO_DB": "test_db",
            "BLUEPRINT_COLL": "blueprints",
            "BLUEPRINT_VERSIONS_COLL": "custom_versions",  # custom name
        },
        clear=False,
    )
    def test_custom_versions_collection_env_var(self):
        bp_col = _make_mock_collection("bp_col")
        ver_col = _make_mock_collection("ver_col")
        db = _make_mock_db(bp_col, ver_col)
        mock_client = _make_mock_mongo_client(db)

        with patch("bootstrap.container.MongoClient", return_value=mock_client):
            from bootstrap.container import AppConfig, AppContainer

            config = AppConfig()
            assert config.blueprint_versions_coll == "custom_versions"

    @patch.dict(
        "os.environ",
        {
            "MONGO_URI": "mongodb://localhost:27017",
            "MONGO_DB": "test_db",
        },
        clear=False,
    )
    def test_blueprint_versions_coll_default_value(self):
        """BLUEPRINT_VERSIONS_COLL must default to 'blueprint_versions'."""
        with patch("bootstrap.container.MongoClient", return_value=MagicMock()):
            from bootstrap.container import AppConfig

            config = AppConfig()
            assert config.blueprint_versions_coll == "blueprint_versions"

    @patch.dict(
        "os.environ",
        {
            "MONGO_URI": "mongodb://localhost:27017",
            "MONGO_DB": "test_db",
        },
        clear=False,
    )
    def test_service_version_methods_are_callable(self):
        """list_versions, load_version, restore_version must be accessible."""
        bp_col = _make_mock_collection("bp_col")
        ver_col = _make_mock_collection("ver_col")
        db = _make_mock_db(bp_col, ver_col)
        mock_client = _make_mock_mongo_client(db)

        with patch("bootstrap.container.MongoClient", return_value=mock_client):
            from bootstrap.container import AppContainer

            container = AppContainer()
            svc = container.blueprint_service

        assert callable(getattr(svc, "list_versions", None))
        assert callable(getattr(svc, "load_version", None))
        assert callable(getattr(svc, "restore_version", None))

    @patch.dict(
        "os.environ",
        {
            "MONGO_URI": "mongodb://localhost:27017",
            "MONGO_DB": "test_db",
        },
        clear=False,
    )
    def test_attach_to_flask_app_sets_container_and_service(self):
        """attach_to_flask_app must set both app.container and app.blueprint_service."""
        bp_col = _make_mock_collection("bp_col")
        ver_col = _make_mock_collection("ver_col")
        db = _make_mock_db(bp_col, ver_col)
        mock_client = _make_mock_mongo_client(db)

        class _FakeFlaskApp:
            pass

        with patch("bootstrap.container.MongoClient", return_value=mock_client):
            from bootstrap.container import AppContainer

            container = AppContainer()
            fake_app = _FakeFlaskApp()
            container.attach_to_flask_app(fake_app)

        assert hasattr(fake_app, "container")
        assert fake_app.container is container
        assert hasattr(fake_app, "blueprint_service")
        assert fake_app.blueprint_service is container.blueprint_service
