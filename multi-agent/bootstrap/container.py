"""
Dependency-Injection container for the MAS application.

``AppContainer`` reads configuration from environment variables, constructs
all outbound adapters (MongoDB repositories), wires them into the application
service, and exposes a single ``attach_to_flask_app`` helper that makes the
service accessible inside Flask request handlers.

GENIE-1336
----------
* Reads ``BLUEPRINT_VERSIONS_COLL`` env var (default ``blueprint_versions``).
* Constructs ``MongoBlueprintVersionRepository`` and calls ``ensure_indexes()``.
* Injects ``version_repo`` into ``BlueprintService``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import pymongo
from mas.blueprints.service import BlueprintService
from pymongo import MongoClient

from adapters.outbound.mongo.blueprint_repository import \
    MongoBlueprintRepository
from adapters.outbound.mongo.blueprint_version_repository import \
    MongoBlueprintVersionRepository

# ---------------------------------------------------------------------------
# Singleton metaclass
# ---------------------------------------------------------------------------


class SingletonMeta(type):
    """
    Thread-unsafe singleton metaclass.

    Ensures only one instance of ``AppContainer`` is created per process.
    Call ``AppContainer.reset()`` in tests to clear the cached instance.
    """

    _instances: dict = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

    def reset(cls) -> None:
        """Remove the cached singleton instance (test helper)."""
        cls._instances.pop(cls, None)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AppConfig:
    """
    Immutable application configuration sourced from environment variables.

    Environment variables
    ---------------------
    MONGO_URI
        PyMongo connection string (default ``mongodb://localhost:27017``).
    MONGO_DB
        Database name (default ``mas``).
    BLUEPRINT_COLL
        Blueprints collection name (default ``blueprints``).
    BLUEPRINT_VERSIONS_COLL
        Version snapshots collection name (default ``blueprint_versions``).
    """

    mongo_uri: str = field(
        default_factory=lambda: os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    )
    mongo_db: str = field(default_factory=lambda: os.environ.get("MONGO_DB", "mas"))
    blueprint_coll: str = field(
        default_factory=lambda: os.environ.get("BLUEPRINT_COLL", "blueprints")
    )
    blueprint_versions_coll: str = field(
        default_factory=lambda: os.environ.get(
            "BLUEPRINT_VERSIONS_COLL", "blueprint_versions"
        )
    )


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


class AppContainer(metaclass=SingletonMeta):
    """
    Application-level DI container (singleton).

    Usage::

        container = AppContainer()
        container.attach_to_flask_app(app)

    The ``blueprint_service`` attribute is also publicly accessible for
    programmatic use (e.g. background workers, CLI scripts).

    Call ``AppContainer.reset()`` in tests to clear the singleton cache.
    """

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self._config = config or AppConfig()
        self._mongo_client: Optional[pymongo.MongoClient] = None
        self.blueprint_service: Optional[BlueprintService] = None
        self.blueprint_repo: Optional[MongoBlueprintRepository] = None
        self.blueprint_version_repo: Optional[MongoBlueprintVersionRepository] = None
        self._build()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def attach_to_flask_app(self, app) -> None:
        """
        Make the container and ``BlueprintService`` available inside Flask
        request handlers as ``current_app.container`` and
        ``current_app.blueprint_service``.

        Call this once during Flask app setup, after ``_build`` has run.
        """
        app.container = self
        app.blueprint_service = self.blueprint_service

    def teardown(self) -> None:
        """Close MongoDB connection pool (useful in tests and graceful shutdown)."""
        if self._mongo_client is not None:
            self._mongo_client.close()
            self._mongo_client = None

    # ------------------------------------------------------------------
    # Internal wiring
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """
        Wire the full dependency graph.

        Order:
        1. Connect to MongoDB.
        2. Build outbound adapters (repositories).
        3. Ensure indexes on both collections.
        4. Build the application service with all dependencies.
        """
        cfg = self._config

        # 1. MongoDB connection
        self._mongo_client = MongoClient(cfg.mongo_uri)
        db = self._mongo_client[cfg.mongo_db]

        # 2. Outbound adapters
        self.blueprint_repo = MongoBlueprintRepository(col=db[cfg.blueprint_coll])
        self.blueprint_version_repo = MongoBlueprintVersionRepository(
            col=db[cfg.blueprint_versions_coll]
        )

        # 3. Indexes are created in MongoBlueprintVersionRepository.__init__()

        # 4. Application service  (GENIE-1336: version_repo is now wired)
        self.blueprint_service = BlueprintService(
            repo=self.blueprint_repo,
            # resolver, validation_service, card_service, auth_service
            # are wired here in production; omitted for clarity.
            version_repo=self.blueprint_version_repo,
        )
