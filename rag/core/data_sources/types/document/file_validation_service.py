"""
File Validation Service for Document Upload Operations

This service handles pre-upload validation of files including:
- File extension validation against supported types
- File size validation against maximum allowed size
- File name duplicate detection (allowing re-upload of FAILED documents)

IMPORTANT: This validation is designed to be called BEFORE files are uploaded to the server.
The UI calls this endpoint with file metadata (name, size) to validate files before uploading.
Files that pass validation can be uploaded with skip_validation=true on the embed endpoint.

Matches backend/services/documents/file_validation_service.py logic.
"""
from typing import Any, Dict, List
from dataclasses import dataclass

from infrastructure.sources.document.config import DocConfigManager
from infrastructure.sources.document.validator.name_duplicate_checker import NameDuplicateCheckerAdapter
from shared.logger import logger


# Maximum file size in bytes (50 MB)
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


@dataclass
class FileValidationError:
    """Represents a validation error for a single file."""
    file_name: str
    error_type: str  # 'extension', 'size', 'duplicate'
    message: str


@dataclass 
class FileValidationResult:
    """Result of file validation."""
    valid_files: List[Dict[str, Any]]
    errors: List[FileValidationError]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid_files": self.valid_files,
            "errors": [
                {
                    "file_name": e.file_name,
                    "error_type": e.error_type,
                    "message": e.message
                }
                for e in self.errors
            ],
            "has_errors": len(self.errors) > 0
        }


class FileValidationService:
    """
    Service for validating files before upload.
    
    This service performs the following validations:
    1. File extension - must be in the list of supported extensions
    2. File size - must not exceed MAX_FILE_SIZE_BYTES (50 MB)
    3. Duplicate name - checks if a file with the same normalized name exists
       for the user (but allows re-upload if existing document has FAILED status)
    
    Usage:
        service = FileValidationService(
            username="john_doe",
            config_manager=DocConfigManager(),
            name_checker=NameDuplicateCheckerAdapter(storage)
        )
        result = service.validate([
            {"name": "document.pdf", "size": 1024000},
            {"name": "invalid.exe", "size": 500000},
        ])
    """
    
    def __init__(
        self,
        username: str,
        config_manager: DocConfigManager,
        name_checker: NameDuplicateCheckerAdapter,
    ):
        """
        Initialize the validation service.
        
        Args:
            username: The username of the person uploading files
            config_manager: Document configuration manager for supported extensions
            name_checker: Name duplicate checker adapter
        """
        self.username = username
        self.config_manager = config_manager
        self.supported_extensions = self.config_manager.get_supported_file_types()
        self.name_checker = name_checker
        
    def _is_extension_supported(self, filename: str) -> bool:
        """Check if the file extension is supported."""
        extension = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
        return f".{extension}" in self.supported_extensions
    
    def _is_size_valid(self, size_bytes: int) -> bool:
        """Check if the file size is within limits."""
        return size_bytes <= MAX_FILE_SIZE_BYTES
    
    def validate(
        self, 
        files: List[Dict[str, Any]],
        check_duplicates: bool = True
    ) -> FileValidationResult:
        """
        Validate a list of files for upload.
        
        Args:
            files: List of file metadata dictionaries with 'name' and 'size' keys.
                   Example: [{"name": "doc.pdf", "size": 1024000}]
            check_duplicates: Whether to check for duplicate filenames (default True)
            
        Returns:
            FileValidationResult containing valid files and errors.
        """
        valid_files: List[Dict[str, Any]] = []
        errors: List[FileValidationError] = []
        pending_normalized_names: set = set()
        
        # Fetch existing documents once for duplicate checking (batch optimization)
        existing_docs = (
            self.name_checker.get_existing_documents_for_user(self.username) 
            if check_duplicates else []
        )
        
        for file_info in files:
            filename = file_info.get("name", "")
            file_size = file_info.get("size", 0)
            
            # Track all validation errors for this file
            file_errors: List[FileValidationError] = []
            
            # Validate extension
            if not self._is_extension_supported(filename):
                extension = filename.rsplit('.', 1)[-1] if '.' in filename else 'unknown'
                file_errors.append(FileValidationError(
                    file_name=filename,
                    error_type="extension",
                    message=f"File type '.{extension}' is not supported. Supported types: {', '.join(self.supported_extensions)}"
                ))
            
            # Validate size
            if not self._is_size_valid(file_size):
                size_mb = file_size / (1024 * 1024)
                max_size_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
                file_errors.append(FileValidationError(
                    file_name=filename,
                    error_type="size",
                    message=f"File size ({size_mb:.2f} MB) exceeds maximum allowed ({max_size_mb:.0f} MB)"
                ))
            
            # Validate duplicate name (only if no other errors and duplicates check enabled)
            if check_duplicates and not file_errors:
                normalized_name = self.name_checker.normalize_filename(filename)
                
                # First check if already in the pending batch (same upload)
                if normalized_name in pending_normalized_names:
                    file_errors.append(FileValidationError(
                        file_name=filename,
                        error_type="duplicate",
                        message="A file with the same name is already selected for upload"
                    ))
                else:
                    # Then check against existing documents using shared checker
                    is_duplicate, status = self.name_checker.find_blocking_duplicate(
                        normalized_name, 
                        existing_docs
                    )
                    
                    if is_duplicate:
                        file_errors.append(FileValidationError(
                            file_name=filename,
                            error_type="duplicate",
                            message=f"A document with this name already exists (status: {status}). Please rename the file or delete the existing document."
                        ))
            
            # Add to results
            if file_errors:
                errors.extend(file_errors)
            else:
                normalized_name = self.name_checker.normalize_filename(filename)
                pending_normalized_names.add(normalized_name)
                valid_files.append({
                    "name": filename,
                    "normalized_name": normalized_name,
                    "size": file_size
                })
        
        logger.info(
            f"File validation complete for user {self.username}: "
            f"{len(valid_files)} valid, {len(errors)} errors"
        )
        
        return FileValidationResult(valid_files=valid_files, errors=errors)
