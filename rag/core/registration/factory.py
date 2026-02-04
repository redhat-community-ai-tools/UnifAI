"""Registration factory - creates registration instances."""
from __future__ import annotations

from typing import Any, Dict

from core.registration.domain.port import RegistrationPort
from core.data_sources.domain.repository import DataSourceRepository
from core.data_sources.types.document.registration import DocumentRegistration
from core.data_sources.types.slack.registration import SlackRegistration
from core.data_sources.types.document.validators.factory import DocValidators
from core.data_sources.types.slack.validators.factory import SlackValidators


class RegistrationFactory:
    """
    Factory to create registration flows based on data source type.
    
    Supports skip_validation flag for pre-validated files:
    - When skip_validation=False (default): Full validation during registration
    - When skip_validation=True: Only MD5 duplicate check (files pre-validated via /docs/validate)
    """

    def __init__(
        self,
        data_source_repository: DataSourceRepository,
        upload_folder: str,
        doc_validators: DocValidators,
        slack_validators: SlackValidators,
    ) -> None:
        self._data_source_repository = data_source_repository
        self._upload_folder = upload_folder
        self._doc_validators = doc_validators
        self._slack_validators = slack_validators

    def create(
        self,
        source_type: str,
        upload_by: str,
        instance: Dict[str, Any],
        skip_validation: bool = False,
    ) -> RegistrationPort:
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

        if normalized == "slack":
            return SlackRegistration(
                data_source_repository=self._data_source_repository,
                upload_by=upload_by,
                instance=instance,
                slack_validators=self._slack_validators,
                skip_validation=skip_validation,
            )

        if normalized == "document":
            return DocumentRegistration(
                data_source_repository=self._data_source_repository,
                upload_by=upload_by,
                instance=instance,
                upload_folder=self._upload_folder,
                doc_validators=self._doc_validators,
                skip_validation=skip_validation,
            )

        raise ValueError(f"Unsupported source type: {source_type}")
