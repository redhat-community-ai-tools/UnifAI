"""Base registration implementation with common persistence logic."""
from __future__ import annotations

from abc import abstractmethod
from typing import Any, Dict, Tuple
from datetime import datetime

from core.registration.domain.port import RegistrationPort
from core.registration.domain.model import BaseSourceData
from core.data_sources.domain.model import DataSource
from core.data_sources.domain.repository import DataSourceRepository
from shared.logger import logger


class BaseRegistration(RegistrationPort):
    """
    Base implementation for source registration flows.
    
    Provides common persistence and logging logic while delegating
    source-specific behavior to subclasses.
    
    Supports skip_validation flag:
    - When False (default): Full validation is performed (for external API calls)
    - When True: Skip pre-upload validations, only perform content-based validation
      like MD5 duplicate checking (for UI calls that pre-validated via /docs/validate)
    """

    def __init__(
        self,
        data_source_repository: DataSourceRepository,
        upload_by: str,
        instance: Dict[str, Any],
        skip_validation: bool = False,
    ) -> None:
        self._data_source_repository = data_source_repository
        self.upload_by = upload_by
        self.instance = instance
        self.skip_validation = skip_validation

    def register(self) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
        """
        Register a single instance. Returns (registered_source_dict, issue_dict).
        """
        metadata = self._build_metadata()
        type_data = self._build_type_data()

        # Persist via repository
        self._persist(type_data)

        # Build response
        registered_source = self._build_registered_source(metadata, type_data)

        # Log
        self._log_registered()

        return registered_source, None

    def _persist(self, type_data: Dict[str, Any]) -> None:
        """Persist the source using the repository port."""
        now = datetime.utcnow()
        source = DataSource(
            source_id=self.source_data.source_id,
            source_name=self.source_data.source_name,
            source_type=self.DATA_SOURCE_TYPE,
            pipeline_id=self.source_data.pipeline_id,
            upload_by=self.upload_by,
            created_at=now,
            last_sync_at=now,
            tags=self.instance.get("tags", []),
            type_data=type_data,
        )
        self._data_source_repository.save(source)

    def _build_registered_source(
        self,
        metadata: Any,
        type_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the registered source response dict."""
        return {
            "pipeline_id": self.source_data.pipeline_id,
            "metadata": metadata.__dict__ if hasattr(metadata, "__dict__") else metadata,
            "source_type": self.DATA_SOURCE_TYPE,
            "upload_by": self.upload_by,
            "type_data": type_data,
        }

    def _log_registered(self) -> None:
        """Log the registration."""
        metadata_info = f" with form data: {self.source_data.form_data}" if self.source_data.form_data else ""
        logger.info(
            f"Registered {self.DATA_SOURCE_TYPE} source: {self.source_data.source_name} "
            f"with pipeline_id: {self.source_data.pipeline_id}{metadata_info}"
        )

    @abstractmethod
    def _build_metadata(self) -> Any:
        """Build source-specific metadata object."""
        ...

    @abstractmethod
    def _build_type_data(self) -> Dict[str, Any]:
        """Build source-specific type data dict."""
        ...
