"""
Read-only access to the backend's ``admin_config`` MongoDB collection.

The backend ``AdminConfigService`` owns writes to this collection via the
admin panel (``config.section.update``).  MAS only needs to **read** the
``admin_users`` section to enforce the same admin gate.

Follows the same repository pattern as ``MongoAdminConfigRepository`` in
the backend, but exposes only the ``is_admin`` check.
"""
import logging

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
    """

    def __init__(
        self,
        mongodb_ip: str = "0.0.0.0",
        mongodb_port: str = "27017",
        db_name: str = "config",
        coll_name: str = "admin_config",
    ):
        mongo_uri = f"mongodb://{mongodb_ip}:{mongodb_port}/"
        client = pymongo.MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        self._col = client[db_name][coll_name]

    def is_admin(self, username: str) -> bool:
        """Return *True* if *username* appears in the stored admin list."""
        try:
            doc = self._col.find_one({"key": "admin_users"})
            if doc and doc.get("value"):
                admin_usernames = doc["value"].get("admin_usernames", [])
                return username.lower() in [u.lower() for u in admin_usernames]
        except pymongo.errors.PyMongoError:
            logger.warning("Could not read admin config from DB", exc_info=True)
        return False
