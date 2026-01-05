"""
Name Duplicate Checker for Document Upload Operations

This service provides the core logic for checking if a document with the same 
normalized filename already exists for a user. It's used by both:
- FileValidationService (pre-upload validation)
- NameDuplicateValidator (registration-time validation)

A document is considered a blocking duplicate if:
- It has the same normalized filename (using secure_filename)
- It belongs to the same user (upload_by)
- Its pipeline status is NOT 'failed' (allows retry of failed uploads)

Rationale:
When a user defines a Retriever, they may filter documents based on file names
in order to reduce the scope of the retrieval operation. Allowing multiple files
with the same name uploaded by the same user would introduce ambiguity in this
filtering logic and make retrieval behavior unclear.

Therefore, we enforce uniqueness at the filter level:
{FILE_NAME}/{UPLOADED_BY} must be unique.
"""

from typing import Any, Dict, List, Optional, Tuple

from config.constants import DataSource, PipelineStatus
from global_utils.utils import secure_filename


class NameDuplicateChecker:
    """
    Domain service for detecting duplicate document names per user.
    
    This service depends on a storage facade that exposes:
    - get_source_by_query: to fetch existing documents
    - get_pipeline_status: to check if existing documents have failed status
    
    Usage:
        checker = NameDuplicateChecker(mongo_storage)
        existing_docs = checker.get_existing_documents_for_user("john_doe")
        is_dup, status = checker.is_duplicate_name("report.pdf", existing_docs)
    """

    def __init__(self, storage: Any):
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
                "source_type": DataSource.DOCUMENT.upper_name,
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
            - is_blocking_duplicate: True if a blocking duplicate exists
            - existing_doc_status: Status of the blocking document (if any)
            
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
                if status != PipelineStatus.FAILED.value:
                    return True, status
                    
        return False, None

    def is_duplicate_name(
        self,
        filename: str,
        username: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Convenience method to check if a filename is a duplicate for a user.
        
        This method fetches existing documents and checks for duplicates in one call.
        Use find_blocking_duplicate directly if you already have the existing docs
        (e.g., for batch validation).
        
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

