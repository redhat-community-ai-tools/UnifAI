from typing import Any, Dict, List, Optional

from config.constants import DataSource, PipelineStatus
from global_utils.utils import compute_file_md5


# Statuses that should NOT block duplicate uploads (allow retry of failed uploads)
NON_BLOCKING_STATUSES = {PipelineStatus.FAILED.value}


class DocumentDuplicateChecker:
    """
    Domain service for detecting duplicate documents by content hash (MD5).

    This service depends on a storage facade that exposes `get_source_by_query`.
    It keeps persistence concerns out of validators and orchestrators.
    
    A document is considered a duplicate if an existing document with the same 
    MD5 hash exists and is NOT in FAILED status. Documents with FAILED status 
    are not considered duplicates, allowing users to retry failed uploads.
    Documents that are pending, processing, or completed will block duplicates.
    """

    def __init__(self, storage: Any):
        self._storage = storage

    def find_existing_by_md5(
        self,
        md5: str,
        *,
        source_type: str = DataSource.DOCUMENT.upper_name,
        extra_filters: Optional[Dict[str, Any]] = None,
        only_blocking: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Find existing documents with the same MD5 hash.
        
        Args:
            md5: The MD5 hash to search for
            source_type: The type of source to filter by
            extra_filters: Additional query filters
            only_blocking: If True, only return documents that would block 
                          a new upload (i.e., those NOT in FAILED status)
        
        Returns:
            List of matching source documents
        """
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
            sources = result if isinstance(result, list) else []
            
            if not only_blocking or not sources:
                return sources
            
            # Filter to only include sources with blocking status (NOT FAILED)
            # This ensures documents that are pending, processing, or completed block duplicates
            blocking_sources = []
            for source in sources:
                pipeline_id = source.get("pipeline_id")
                status = self._storage.get_pipeline_status(pipeline_id) if hasattr(self._storage, "get_pipeline_status") else None
                if status not in NON_BLOCKING_STATUSES:
                    blocking_sources.append(source)
            
            return blocking_sources
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

        A document is considered a duplicate if there's an existing document 
        with the same MD5 hash that is NOT in FAILED status. This means:
        - Pending, processing, and completed documents block duplicates
        - Only FAILED uploads do not block re-uploads (allowing retry)

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

        # Consider documents as blocking duplicates unless they're in FAILED status
        existing = self.find_existing_by_md5(
            md5_hash, 
            source_type=source_type, 
            extra_filters=extra_filters,
            only_blocking=True
        )
        return len(existing) > 0


