"""
File Extension Validator

Validates that uploaded files have supported extensions.
This validator is used during registration for external API calls
(when skip_validation=False).

For UI uploads, extension validation happens in /docs/validate before upload.
"""

from typing import Optional, Any, Tuple
from common.interfaces import DataSourceValidator, ValidationIssue
from data_sources.docs.doc_config_manager import DocConfigManager


class ExtensionValidator(DataSourceValidator):
    """
    Validates file extension against supported types.
    
    This validator checks if the file extension is in the list of
    supported extensions configured in DocConfigManager.
    """
    name = "ExtensionValidator"
    error_message = "File type '.{extension}' is not supported. Supported types: {supported}"
    error_message_key = "Unsupported file type"

    def __init__(self) -> None:
        self.config_manager = DocConfigManager()
        self.supported_extensions = self.config_manager.get_supported_file_types()

    def validate(self, **kwargs: Any) -> Tuple[bool, Optional[ValidationIssue]]:
        """
        Validate the file extension.
        
        Args:
            source_name: The filename to validate
            
        Returns:
            Tuple of (is_valid, issue). issue is None if valid.
        """
        source_name = kwargs.get("source_name", "")
        
        if not source_name:
            return True, None  # No filename, let other validators handle
        
        # Extract extension
        extension = ""
        if "." in source_name:
            extension = source_name.rsplit(".", 1)[-1].lower()
        
        if not extension or f".{extension}" not in self.supported_extensions:
            supported_str = ", ".join(self.supported_extensions)
            return False, self.build_issue(
                self.error_message.format(
                    extension=extension or "unknown",
                    supported=supported_str
                )
            )
        
        return True, None

