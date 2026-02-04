"""
File Size Validator

Validates that uploaded files don't exceed the maximum allowed size.
This validator is used during registration for external API calls
(when skip_validation=False).

For UI uploads, size validation happens in /docs/validate before upload.
"""

import os
from typing import Optional, Any, Tuple

from core.validation.domain.port import DataSourceValidator
from core.validation.domain.model import ValidationIssue
from shared.logger import logger


# Maximum file size in bytes (50 MB default)
DEFAULT_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


class SizeValidator(DataSourceValidator):
    """
    Validates file size against maximum allowed.
    
    This validator checks if the file size is within the configured
    maximum limit (50 MB by default).
    """
    name = "SizeValidator"
    error_message = "File size ({size_mb:.2f} MB) exceeds maximum allowed ({max_mb:.0f} MB)"
    error_message_key = "File too large"

    def __init__(self, max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES) -> None:
        self._max_file_size_bytes = max_file_size_bytes

    def validate(self, **kwargs: Any) -> Tuple[bool, Optional[ValidationIssue]]:
        """
        Validate the file size.
        
        Args:
            doc_path: Path to the uploaded file on disk
            
        Returns:
            Tuple of (is_valid, issue). issue is None if valid.
        """
        doc_path = kwargs.get("doc_path", "")
        
        if not doc_path or not os.path.exists(doc_path):
            return True, None  # File doesn't exist, let other validators handle
        
        try:
            file_size = os.path.getsize(doc_path)
            
            if file_size > self._max_file_size_bytes:
                size_mb = file_size / (1024 * 1024)
                max_mb = self._max_file_size_bytes / (1024 * 1024)
                return False, self.build_issue(
                    self.error_message.format(size_mb=size_mb, max_mb=max_mb)
                )
        except Exception as e:
            logger.warning(
                f"Size validation failed for {doc_path}, "
                f"allowing upload: {e}"
            )
            return True, None
        
        return True, None
