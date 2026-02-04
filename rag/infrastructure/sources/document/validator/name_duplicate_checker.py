"""Infrastructure adapter for name duplicate checking.

This adapter implements the NameDuplicateCheckerPort using MongoDB storage.
It preserves the exact same logic as the original NameDuplicateChecker
from backend/services/documents/name_duplicate_checker.py.
"""
from typing import Any, Dict, List, Optional, Tuple

from global_utils.utils import secure_filename


class NameDuplicateCheckerAdapter:
    """
    MongoDB-based name duplicate checker implementation.
    
    A document is considered a blocking duplicate if:
    - It has the same normalized filename (using secure_filename)
    - It belongs to the same user (upload_by)
    - Its pipeline status is NOT 'FAILED' (allows retry of failed uploads)
    """

    def __init__(self, storage: Any) -> None:
        self._storage = storage

    def normalize_filename(self, filename: str) -> str:
        """
        Normalize filename for duplicate checking.
        Uses secure_filename to ensure consistent comparison.
        """
        return secure_filename(filename)

    def get_existing_documents_for_user(self, username: str) -> List[Dict[str, Any]]:
        """
        Get existing documents for a user.
        
        Args:
            username: The username to fetch documents for
            
        Returns:
            List of document dictionaries for the user
        """
        if not hasattr(self._storage, "get_source_by_query"):
            return []
            
        try:
            query = {
                "source_type": "DOCUMENT",
                "upload_by": username
            }
            result = self._storage.get_source_by_query(query)
            return result if isinstance(result, list) else []
        except Exception:
            return []

    def get_pipeline_status(self, pipeline_id: str) -> Optional[str]:
        """
        Get the status of a pipeline by its ID.
        
        Args:
            pipeline_id: The pipeline ID to look up
            
        Returns:
            The pipeline status string, or None if not found
        """
        if not pipeline_id:
            return None
            
        if hasattr(self._storage, "get_pipeline_status"):
            return self._storage.get_pipeline_status(pipeline_id)
        return None

    def find_blocking_duplicate(
        self,
        normalized_name: str,
        existing_docs: List[Dict[str, Any]],
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a normalized filename has a blocking duplicate in existing docs.
        
        Args:
            normalized_name: The normalized filename to check
            existing_docs: List of existing documents to check against
            
        Returns:
            Tuple of (is_blocking_duplicate, existing_doc_status)
            
        Note: Documents with FAILED status are NOT considered blocking duplicates,
        allowing users to retry failed uploads.
        """
        for doc in existing_docs:
            doc_name = doc.get("source_name", "")
            doc_normalized = self.normalize_filename(doc_name)
            
            if doc_normalized == normalized_name:
                pipeline_id = doc.get("pipeline_id", "")
                status = self.get_pipeline_status(pipeline_id)
                
                # Only block if existing document is NOT failed
                if status != "FAILED":
                    return True, status
                    
        return False, None

    def is_duplicate_name(
        self,
        filename: str,
        username: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Convenience method to check if a filename is a duplicate for a user.
        
        Args:
            filename: The filename to check (will be normalized)
            username: The username to check duplicates for
            
        Returns:
            Tuple of (is_blocking_duplicate, existing_doc_status)
        """
        if not filename:
            return False, None
            
        normalized_name = self.normalize_filename(filename)
        existing_docs = self.get_existing_documents_for_user(username)
        return self.find_blocking_duplicate(normalized_name, existing_docs)
