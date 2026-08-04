"""
Read-only access to the backend's ``admin_config`` MongoDB collection.

The backend ``AdminConfigService`` owns writes to this collection via the
admin panel (``config.section.update``).  MAS only needs to **read** the
``admin_users`` section to enforce the same admin gate.

Follows the same repository pattern as ``MongoAdminConfigRepository`` in
the backend, but exposes only the ``is_admin`` check.
"""
import logging
import time
from typing import Optional

import pymongo

from mas.core.identity.ports import AdminConfigReaderPort

logger = logging.getLogger(__name__)


class MongoAdminConfigReader(AdminConfigReaderPort):
    """Read-only reader for the centralized admin config collection.

    Args:
        mongodb_ip: MongoDB host.
        mongodb_port: MongoDB port.
        db_name: Database that holds the ``admin_config`` collection
                 (defaults to ``"config"`` — the backend's database).
        coll_name: Collection name (defaults to ``"admin_config"``).
        cache_ttl_seconds: How long a fetched admin list is reused across
                 requests/processes before re-reading Mongo. Every
                 admin-gated request otherwise triggers a read; a short TTL
                 keeps that off the hot path without making admin-list
                 changes take unreasonably long to propagate.
    """

    def __init__(
        self,
        mongodb_ip: str = "0.0.0.0",
        mongodb_port: str = "27017",
        db_name: str = "config",
        coll_name: str = "admin_config",
        cache_ttl_seconds: float = 30.0,
    ):
        mongo_uri = f"mongodb://{mongodb_ip}:{mongodb_port}/"
        client = pymongo.MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        self._col = client[db_name][coll_name]
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cached_admins: Optional[set[str]] = None
        self._cached_at: float = 0.0
        self._last_failure_at: float = 0.0

    def is_admin(self, username: str) -> bool:
        """Return *True* if *username* appears in the stored admin list."""
        admin_usernames = self._get_admin_usernames()
        if admin_usernames is None:
            return False
        return username.lower() in admin_usernames

    def _get_admin_usernames(self) -> Optional[set[str]]:
        """Fetch the admin username set from Mongo, with TTL caching.

        Unlike the backend's ``AdminConfigService.is_admin()``, this
        reader does **not** fall back to the template-defined default
        when no ``admin_users`` document exists yet in MongoDB.  During
        the bootstrap window (first deploy → first admin-panel save) the
        Mongo document is absent, so this reader returns an empty set
        and ``is_admin()`` returns False for everyone.  The static
        ``admin_allowed_users`` Flask-config fallback in
        ``decorators.is_admin_user`` covers this gap: any username in
        that list is still granted admin access even before the Mongo
        document is populated.  After the first admin-panel save writes
        the document, MAS and the backend agree.
        """
        now = time.monotonic()
        if (
            self._cached_admins is not None
            and (now - self._cached_at) < self._cache_ttl_seconds
        ):
            return self._cached_admins

        # After a failure, back off for cache_ttl_seconds before retrying
        # to avoid flooding logs and adding latency on the hot path.
        if self._last_failure_at and (now - self._last_failure_at) < self._cache_ttl_seconds:
            return self._cached_admins

        try:
            doc = self._col.find_one({"key": "admin_users"})
            admin_usernames = set()
            if doc and doc.get("value"):
                admin_usernames = {u.lower() for u in doc["value"].get("admin_usernames", [])}
            self._cached_admins = admin_usernames
            self._cached_at = now
            self._last_failure_at = 0.0
        except pymongo.errors.PyMongoError:
            logger.warning("Could not read admin config from DB", exc_info=True)
            self._last_failure_at = now
        return self._cached_admins
