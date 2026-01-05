from __future__ import annotations

from typing import Any, Dict

from config.constants import DataSource

from .base import RegistrationBase
from .document import DocumentRegistration
from .slack import SlackRegistration


class RegistrationFactory:
    """
    Factory to create registration flows based on data source type.
    
    Supports skip_validation flag for pre-validated files:
    - When skip_validation=False (default): Full validation during registration
    - When skip_validation=True: Only MD5 duplicate check (files pre-validated via /docs/validate)
    """

    def __init__(self, mongo_storage: Any) -> None:
        self.mongo_storage = mongo_storage

    def create(
        self, 
        source_type: str, 
        upload_by: str, 
        instance: Dict[str, Any],
        skip_validation: bool = False
    ) -> RegistrationBase:
        """
        Create a registration instance for the given source type.
        
        Args:
            source_type: Type of data source (e.g., 'slack', 'document')
            upload_by: Username of the person uploading
            instance: Data instance to register
            skip_validation: If True, skip pre-upload validations (extension, size, name).
                            MD5 duplicate check is always performed.
        """
        normalized = (source_type or "").strip().lower()

        if normalized == DataSource.SLACK.value:
            return SlackRegistration(self.mongo_storage, upload_by, instance, skip_validation)

        if normalized == DataSource.DOCUMENT.value:
            return DocumentRegistration(self.mongo_storage, upload_by, instance, skip_validation)

        raise ValueError(f"Unsupported source type: {source_type}")


