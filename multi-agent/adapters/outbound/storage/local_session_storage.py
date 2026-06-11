import logging
import os
import shutil

from mas.session.storage.ports import SessionStorageCleaner

logger = logging.getLogger(__name__)


class LocalSessionStorageCleaner(SessionStorageCleaner):
    """Cleans up session working directories on the local filesystem."""

    def __init__(self, base_path: str) -> None:
        self._base_path = base_path

    def cleanup(self, session_id: str) -> None:
        session_dir = os.path.join(self._base_path, session_id)
        if not os.path.isdir(session_dir):
            return
        try:
            shutil.rmtree(session_dir)
            logger.info("Cleaned up session storage: %s", session_dir)
        except Exception:
            logger.warning(
                "Failed to clean up session storage: %s",
                session_dir, exc_info=True,
            )
