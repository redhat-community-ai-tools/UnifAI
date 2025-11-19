from typing import Any, Dict, List, Optional

from config.constants import DataSource
from utils.file_hash import compute_file_md5


class DocumentDuplicateChecker:
    """
    Domain service for detecting duplicate documents by content hash (MD5).

    This service depends on a storage facade that exposes `get_source_by_query`.
    It keeps persistence concerns out of validators and orchestrators.
    """

    def __init__(self, storage: Any):
        self._storage = storage

    def find_existing_by_md5(
        self,
        md5: str,
        *,
        source_type: str = DataSource.DOCUMENT.upper_name,
        extra_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not hasattr(self._storage, "get_source_by_query"):
            return []

        query: Dict[str, Any] = {
            "source_type": source_type,
            "type_data.md5": md5,
        }
        if extra_filters:
            query.update(extra_filters)

        try:
            result = self._storage.get_source_by_query(query)
            return result if isinstance(result, list) else []
        except Exception:
            return []

    def is_duplicate(
        self,
        doc: Dict[str, Any],
        *,
        source_type: str = DataSource.DOCUMENT.upper_name,
        extra_filters: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Determine if the provided document is a duplicate by MD5.

        Accepts a doc dict and will attempt to compute or read the MD5 from:
        - doc["md5"]
        - doc["type_data.md5"]
        - compute from doc["doc_path"] or doc["path"] if present
        """
        md5_hash: Optional[str] = None
        if isinstance(doc, dict):
            md5_hash = doc.get("md5") or doc.get("type_data.md5")
            if not md5_hash:
                doc_path = doc.get("doc_path") or doc.get("path")
                if isinstance(doc_path, str):
                    try:
                        md5_hash = compute_file_md5(doc_path)
                    except Exception:
                        md5_hash = None

        if not md5_hash:
            return False

        existing = self.find_existing_by_md5(md5_hash, source_type=source_type, extra_filters=extra_filters)
        return len(existing) > 0


