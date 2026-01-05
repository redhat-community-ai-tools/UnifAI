"""
File Name Duplicate Validator

Validates that a file with the same normalized name doesn't already exist
for the user (unless the existing document has FAILED status).

This validator is used during registration for external API calls
(when skip_validation=False).
For UI uploads, name duplicate validation happens in /docs/validate before upload.

Note: This is different from the MD5 DuplicateValidator, which checks file content.
This validator checks file *names* to prevent ambiguity and confusion.

Rationale:
When a user defines a Retriever, they may filter documents based on file names
in order to reduce the scope of the retrieval operation. Allowing multiple files
with the same name uploaded by the same user would introduce ambiguity in this
filtering logic and make retrieval behavior unclear.

Therefore, we enforce uniqueness at the filter level:
{FILE_NAME}/{UPLOADED_BY} must be unique.

"""

from typing import Optional, Any, Tuple
from common.interfaces import DataSourceValidator, ValidationIssue
from services.documents.name_duplicate_checker import NameDuplicateChecker
from utils.storage.mongo.mongo_helpers import get_mongo_storage


class NameDuplicateValidator(DataSourceValidator):
    """
    Validates that no document with the same normalized filename exists for the user.
    
    This validator:
    - Normalizes the filename using secure_filename
    - Checks if a document with the same normalized name exists for the user
    - Allows re-upload if the existing document has FAILED status
    
    This is different from MD5 duplicate checking - this checks names, not content.
    """
    name = "NameDuplicateValidator"
    error_message = "A document named '{source_name}' already exists (status: {status}). Please rename the file or delete the existing document."
    error_message_key = "Duplicate filename"

    def __init__(self) -> None:
        self.duplicate_checker = NameDuplicateChecker(get_mongo_storage())

    def validate(self, **kwargs: Any) -> Tuple[bool, Optional[ValidationIssue]]:
        """
        Validate that no duplicate filename exists.
        
        Args:
            source_name: The filename to validate
            upload_by: The username of the uploader (passed via instance context)
            
        Returns:
            Tuple of (is_valid, issue). issue is None if valid.
        """
        source_name = kwargs.get("source_name", "")
        upload_by = kwargs.get("upload_by", "")
        
        if not source_name:
            return True, None
        
        is_duplicate, status = self.duplicate_checker.is_duplicate_name(
            filename=source_name,
            username=upload_by
        )
        
        if is_duplicate:
            return False, self.build_issue(
                self.error_message.format(
                    source_name=source_name,
                    status=status or "unknown"
                )
            )
        
        return True, None
